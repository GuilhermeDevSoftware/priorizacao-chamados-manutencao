"""Cadastro local integrado: banco e imagens temporários, sem API externa real."""
from __future__ import annotations

from datetime import datetime
import io
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch

from PIL import Image, ImageDraw
import pytest

from app import create_app

TOKEN_TESTE = "credencial-ficticia-de-teste"


@pytest.fixture
def config(tmp_path):
    return {"TESTING": True, "OPENAI_API_KEY": "", "DATABASE_PATH": str(tmp_path / "dados" / "chamados.sqlite3"),
            "UPLOAD_FOLDER": str(tmp_path / "uploads"), "PRIORIZA_ADMIN_TOKEN": TOKEN_TESTE}


@pytest.fixture
def client(config):
    return create_app(config).test_client()


def foto_sintetica(formato="JPEG", tamanho=(800, 600)):
    """Desenho de fios para testar bytes válidos; não é uma fotografia real."""
    img = Image.new("RGB", tamanho, "#ece7df")
    desenho = ImageDraw.Draw(img)
    desenho.rectangle((20, 20, 170, 140), fill="#8c9399")
    for deslocamento, cor in [(0, "#cc3d32"), (25, "#1e588d"), (50, "#2e7d46")]:
        desenho.line([(100+deslocamento, 100), (150+deslocamento, 220), (250+deslocamento, 270)], fill=cor, width=9)
        desenho.line([(250+deslocamento, 270), (280+deslocamento, 280)], fill="#b77935", width=5)
    destino = io.BytesIO()
    img.save(destino, format=formato)
    return destino.getvalue()


def dados(descricao="Vazamento em torneira auxiliar, sem interromper o abastecimento.", equipe="Hidráulica", risco=0):
    return {"descricao": descricao, "local": "Escola fictícia — sala 2", "risco_seguranca": risco,
            "servico_essencial_interrompido": 0, "pessoas_afetadas": 2, "dias_aguardando": 1,
            "recorrente": 0, "equipe_confirmada": equipe, "confirmado": True}


def cadastrar(client, corpo=None, foto=None, nome="foto.jpg"):
    formulario = {"dados": json.dumps(corpo if corpo is not None else dados(), ensure_ascii=False)}
    if foto is not None:
        formulario["foto"] = (io.BytesIO(foto), nome)
    return client.post("/api/chamados", data=formulario, content_type="multipart/form-data")


def editar(client, chamado_id, dados):
    return client.patch(f"/api/chamados/{chamado_id}", json=dados,
                        headers={"Authorization": f"Bearer {TOKEN_TESTE}"})


def test_cadastro_cria_sqlite_e_campos_definidos_no_servidor(client, config):
    with patch("app.requests.post") as externa:
        resposta = cadastrar(client)
    externa.assert_not_called()
    assert resposta.status_code == 201, resposta.json
    registro = resposta.json
    assert isinstance(registro["id"], int) and registro["id"] > 0
    assert registro["status"] == "Aberto"
    assert registro["prioridade_sugerida"] == 0
    assert registro["rotulo_prioridade"] == "Não prioritário"
    assert registro["equipe_sugerida"] == registro["equipe_confirmada"] == "Hidráulica"
    assert registro["justificativa_equipe"]
    assert datetime.fromisoformat(registro["data_abertura"].replace("Z", "+00:00")).tzinfo is not None
    assert registro["foto_caminho"] is None and registro["foto_url"] is None
    assert Path(config["DATABASE_PATH"]).is_file()


def test_fiacao_com_foto_prioritaria_e_normalizacao(client, config):
    corpo = dados("Fiação exposta em corredor de pouca circulação — exemplo fictício.", "Elétrica", risco=1)
    resposta = cadastrar(client, corpo, foto_sintetica("PNG", (2400, 1200)), "../../nome.png")
    assert resposta.status_code == 201, resposta.json
    registro = resposta.json
    assert registro["prioridade_sugerida"] == 2
    assert registro["equipe_sugerida"] == "Elétrica"
    assert ".." not in registro["foto_caminho"]
    assert not Path(registro["foto_caminho"]).is_absolute()
    assert "nome" not in registro["foto_caminho"]
    foto = client.get(f"/api/chamados/{registro['id']}/foto")
    assert foto.status_code == 200 and foto.mimetype == "image/jpeg"
    with Image.open(io.BytesIO(foto.data)) as img:
        assert max(img.size) <= 2048
        assert not img.getexif()
    assert len(list(Path(config["UPLOAD_FOLDER"]).iterdir())) == 1


@pytest.mark.parametrize("descricao,equipe", [
    ("Computador com defeito e impressora sem conexão.", "TI"),
    ("Vazamento na torneira da escola fictícia.", "Hidráulica"),
    ("Fiação exposta junto de um vazamento.", "Triagem geral"),
    ("Problema não identificado na sala.", "Triagem geral"),
])
def test_cenarios_sem_foto_e_sugestao_local(client, descricao, equipe):
    resposta = cadastrar(client, dados(descricao, equipe))
    assert resposta.status_code == 201, resposta.json
    assert resposta.json["equipe_sugerida"] == equipe
    assert resposta.json["foto_caminho"] is None


def test_correcao_manual_preserva_sugestao_e_prioridade(client):
    primeiro = cadastrar(client, dados("Computador sem conexão.", "TI")).json
    resposta = editar(client, primeiro["id"], {"equipe_confirmada": "Elétrica", "status": "Em atendimento"})
    assert resposta.status_code == 200, resposta.json
    assert resposta.json["equipe_sugerida"] == "TI"
    assert resposta.json["equipe_confirmada"] == "Elétrica"
    assert resposta.json["status"] == "Em atendimento"
    assert resposta.json["prioridade_sugerida"] == primeiro["prioridade_sugerida"]
    resolvido = editar(client, primeiro["id"], {"status": "Resolvido"})
    assert resolvido.status_code == 200 and resolvido.json["status"] == "Resolvido"


def test_filtros_usam_equipe_confirmada_e_intersecao(client):
    alvo = cadastrar(client, dados("Computadores de um setor estão sem acesso à rede, prejudicando o trabalho.", "TI")).json
    antigo = cadastrar(client, dados()).json
    recente = cadastrar(client, dados("Computador com defeito.", "TI")).json
    editar(client, alvo["id"], {"equipe_confirmada": "Elétrica", "status": "Em atendimento"})
    resposta = client.get("/api/chamados", query_string={"equipe": "Elétrica", "prioridade": "1", "status": "Em atendimento"})
    assert resposta.status_code == 200, resposta.json
    assert resposta.json["total"] == 1
    assert [x["id"] for x in resposta.json["chamados"]] == [alvo["id"]]
    assert client.get("/api/chamados", query_string={"equipe": "TI", "prioridade": "1"}).json["total"] == 0
    lista = client.get("/api/chamados").json
    assert lista["total"] == 3
    assert [x["id"] for x in lista["chamados"]] == [alvo["id"], antigo["id"], recente["id"]]


def test_dados_e_foto_persistem_apos_nova_instancia_flask(config):
    primeira = create_app(config)
    with primeira.test_client() as c1:
        criado = cadastrar(c1, dados("Fiação exposta — cenário fictício.", "Elétrica", risco=1), foto_sintetica()).json
        foto_antes = c1.get(f"/api/chamados/{criado['id']}/foto").data
    segunda = create_app(config)
    with segunda.test_client() as c2:
        resposta = c2.get(f"/api/chamados/{criado['id']}")
        assert resposta.status_code == 200
        assert resposta.json == criado
        assert c2.get(f"/api/chamados/{criado['id']}/foto").data == foto_antes
        assert c2.get("/api/chamados").json["total"] == 1


@pytest.mark.parametrize("campo,valor", [
    ("descricao", ""), ("descricao", "  "), ("descricao", "x"*2001),
    ("local", ""), ("local", "x"*201), ("risco_seguranca", True),
    ("risco_seguranca", 2), ("pessoas_afetadas", -1), ("dias_aguardando", 1.5),
    ("recorrente", None), ("equipe_confirmada", "Outra"), ("confirmado", False),
    ("confirmado", "true"),
])
def test_cadastro_invalido_nao_grava(client, campo, valor):
    corpo = dados(); corpo[campo] = valor
    resposta = cadastrar(client, corpo)
    assert resposta.status_code == 400, resposta.json
    assert client.get("/api/chamados").json["total"] == 0


@pytest.mark.parametrize("extra,valor", [("prioridade_sugerida", 1), ("status", "Resolvido"), ("id", 99), ("foto_caminho", "../../fora.jpg")])
def test_cliente_nao_define_metadados_do_servidor(client, extra, valor):
    corpo = dados(); corpo[extra] = valor
    assert cadastrar(client, corpo).status_code == 400
    assert client.get("/api/chamados").json["total"] == 0


@pytest.mark.parametrize("arquivo,nome", [(b"nao e imagem", "foto.jpg"), (b'<svg xmlns="http://www.w3.org/2000/svg"></svg>', "foto.svg"), (b"\xff\xd8\xffarquivo incompleto", "foto.jpg")])
def test_imagem_invalida_nao_deixa_registro_ou_arquivo(client, config, arquivo, nome):
    resposta = cadastrar(client, foto=arquivo, nome=nome)
    assert resposta.status_code == 400, resposta.json
    assert client.get("/api/chamados").json["total"] == 0
    assert not list(Path(config["UPLOAD_FOLDER"]).glob("*"))


def test_foto_acima_de_cinco_mib_rejeitada(client):
    resposta = cadastrar(client, foto=b"a"*(5*1024*1024+1))
    assert resposta.status_code == 413, resposta.json
    assert client.get("/api/chamados").json["total"] == 0


def test_gif_valido_disfarcado_de_jpeg_e_rejeitado(client):
    resposta = cadastrar(client, foto=foto_sintetica("GIF"), nome="disfarce.jpg")
    assert resposta.status_code == 400


def test_metadados_exif_sao_removidos(client):
    img = Image.new("RGB", (60, 40), "white")
    exif = Image.Exif(); exif[270] = "Metadado fictício que deve ser removido"; exif[274] = 6
    fluxo = io.BytesIO(); img.save(fluxo, format="JPEG", exif=exif)
    resposta = cadastrar(client, foto=fluxo.getvalue())
    assert resposta.status_code == 201
    foto = client.get(f"/api/chamados/{resposta.json['id']}/foto")
    with Image.open(io.BytesIO(foto.data)) as normalizada:
        assert normalizada.size == (40, 60)
        assert not normalizada.getexif()


def test_limite_de_pixels_impede_descompressao_excessiva(client):
    fluxo = io.BytesIO()
    Image.new("RGB", (5001, 5000), "white").save(fluxo, format="PNG")
    resposta = cadastrar(client, foto=fluxo.getvalue(), nome="grande.png")
    assert resposta.status_code == 413
    assert client.get("/api/chamados").json["total"] == 0


@pytest.mark.parametrize("formato,nome", [("JPEG", "foto.jpg"), ("PNG", "foto.png"), ("WEBP", "foto.webp")])
def test_formatos_permitidos_sao_decodificados(client, formato, nome):
    resposta = cadastrar(client, foto=foto_sintetica(formato), nome=nome)
    assert resposta.status_code == 201, resposta.json


@pytest.mark.parametrize("corpo", [{}, {"status": "Cancelado"}, {"equipe_confirmada": "X"}, {"prioridade_sugerida": 1}, {"descricao": "editar"}, []])
def test_atualizacao_restrita(client, corpo):
    criado = cadastrar(client).json
    resposta = editar(client, criado["id"], corpo)
    assert resposta.status_code == 400
    assert client.get(f"/api/chamados/{criado['id']}").json == criado


def test_inexistentes_e_foto_ausente(client):
    assert client.get("/api/chamados/99999").status_code == 404
    assert editar(client, 99999, {"status": "Resolvido"}).status_code == 404
    assert client.get("/api/chamados/99999/foto").status_code == 404
    criado = cadastrar(client).json
    assert client.get(f"/api/chamados/{criado['id']}/foto").status_code == 404


def test_conteudo_textual_e_filtro_nao_executam_sql(client):
    corpo = dados("Vazamento fictício'); DROP TABLE chamados; --")
    criado = cadastrar(client, corpo).json
    assert criado["descricao"] == corpo["descricao"]
    resposta = client.get("/api/chamados", query_string={"equipe": "TI' OR 1=1 --"})
    assert resposta.status_code == 400 or resposta.json["total"] == 0
    assert client.get("/api/chamados").json["total"] == 1


def test_falha_sqlite_nao_deixa_foto_orfa(client, config):
    # Uma tabela inexistente causa falha real na escrita, sem simular Pillow ou o disco.
    with sqlite3.connect(config["DATABASE_PATH"]) as banco:
        banco.execute("DROP TABLE chamados")
    resposta = cadastrar(client, foto=foto_sintetica())
    assert resposta.status_code == 503, resposta.json
    assert not list(Path(config["UPLOAD_FOLDER"]).glob("*"))


def test_falha_de_leitura_apos_insert_desfaz_registro_e_foto(client, config):
    import storage

    class FalhaLeitura:
        def __init__(self, conexao):
            self.conexao = conexao
            self.inseriu = False

        def execute(self, sql, parametros=()):
            if sql.startswith("INSERT INTO chamados"):
                self.inseriu = True
            elif self.inseriu and sql.startswith("SELECT * FROM chamados"):
                raise sqlite3.OperationalError("Falha de leitura simulada após INSERT")
            return self.conexao.execute(sql, parametros)

        def __getattr__(self, nome):
            return getattr(self.conexao, nome)

    with client.application.app_context():
        conexao = storage.conectar()
        with patch("app.storage.conectar", return_value=FalhaLeitura(conexao)):
            resposta = cadastrar(client, foto=foto_sintetica())
        assert resposta.status_code == 503
    with sqlite3.connect(config["DATABASE_PATH"]) as banco:
        assert banco.execute("SELECT count(*) FROM chamados").fetchone()[0] == 0
    assert not list(Path(config["UPLOAD_FOLDER"]).glob("*"))
