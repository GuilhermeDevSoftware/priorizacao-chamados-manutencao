"""Integração da triagem, fila e auditoria com SQLite descartável."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path
import sqlite3

from itsdangerous import URLSafeTimedSerializer
from PIL import Image
import pytest
import requests

import app as aplicacao


TECLADO = "Solicito substituição de um teclado com uma tecla defeituosa."
REDE = "Computadores de um setor estão sem acesso à rede, prejudicando o trabalho."
FUMACA = "Quadro elétrico emitindo fumaça e cheiro de queimado."
GAS = "Vazamento de gás identificado próximo à cozinha."
ETIQUETA = "Foi verificado que não há vazamento de gás. É apenas necessário substituir uma etiqueta de identificação."
GAVETA = "Solicito um pequeno ajuste em uma gaveta, sem qualquer perigo aparente."
FIACAO = "Fiação elétrica energizada exposta próxima a uma poça de água."
TOKEN = "credencial-exclusiva-de-teste"
AUTORIZACAO = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def bloquear_rede(monkeypatch):
    def falhar(*args, **kwargs):
        pytest.fail("Este conjunto de testes deve executar sem acesso à rede.")

    monkeypatch.setattr(requests.sessions.Session, "request", falhar)


@pytest.fixture
def configuracao(tmp_path):
    return {
        "TESTING": True,
        "OPENAI_API_KEY": "",
        "DATABASE_PATH": str(tmp_path / "chamados.sqlite3"),
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "PRIORIZA_ADMIN_TOKEN": TOKEN,
        "PRIORIZA_ADMIN_NOME": "Responsável fictício",
    }


@pytest.fixture
def cliente(configuracao):
    return aplicacao.create_app(configuracao).test_client()


def campos(descricao=TECLADO, risco=0):
    return {
        "descricao": descricao,
        "risco_seguranca": risco,
        "servico_essencial_interrompido": 0,
        "pessoas_afetadas": 0,
        "dias_aguardando": 0,
        "recorrente": 0,
    }


def enviar(cliente, caminho, dados, foto=None):
    form = {"dados": json.dumps(dados, ensure_ascii=False)}
    if foto is not None:
        form["foto"] = (BytesIO(foto), "foto.jpg")
    return cliente.post(caminho, data=form, content_type="multipart/form-data")


def cadastrar(cliente, descricao=TECLADO, *, risco=0, foto=None, **opcoes):
    dados = {
        **campos(descricao, risco),
        "local": "Bloco de teste",
        "confirmado": True,
        "equipe_confirmada": "TI",
        **opcoes,
    }
    return enviar(cliente, "/api/chamados", dados, foto)


def aprovado(resposta, status):
    assert resposta.status_code == status, resposta.get_json()
    return resposta.get_json()


def listar(cliente, **filtros):
    return aprovado(cliente.get("/api/chamados", query_string=filtros), 200)


def ids(lista):
    return [registro["id"] for registro in lista["chamados"]]


def editar(cliente, id_chamado, **alteracoes):
    return cliente.patch(f"/api/chamados/{id_chamado}", json=alteracoes, headers=AUTORIZACAO)


def jpeg(cor):
    fluxo = BytesIO()
    Image.new("RGB", (12, 12), cor).save(fluxo, format="JPEG")
    return fluxo.getvalue()


@pytest.mark.parametrize(
    "descricao,risco,nivel,rotulo,alerta,contradicao",
    [
        (FUMACA, 0, 2, "Prioritário", True, True),
        (REDE, 0, 1, "Intermediário", False, False),
        (TECLADO, 0, 0, "Não prioritário", False, False),
        (GAS, 0, 2, "Prioritário", True, True),
        (ETIQUETA, 0, 0, "Não prioritário", False, False),
        (GAVETA, 1, 0, "Não prioritário", False, True),
        (FIACAO, 0, 2, "Prioritário", True, True),
    ],
    ids=["A-fumaca", "B-rede", "C-teclado", "D-gas", "E-negacao", "F-contradicao", "fiacao-agua"],
)
def test_casos_obrigatorios_previa_e_cadastro(cliente, descricao, risco, nivel, rotulo, alerta, contradicao):
    previa = aprovado(enviar(cliente, "/api/classificar", campos(descricao, risco)), 200)
    assert previa["prioridade"] == nivel
    assert previa["rotulo"] == rotulo
    assert previa["origem"] == "analise_local"
    assert previa["justificativa"].strip()
    assert previa["alerta_seguranca"] is alerta
    assert previa["contradicao"] is contradicao
    if contradicao:
        assert previa["revisao_necessaria"] is True
    assert listar(cliente)["total"] == 0

    registro = aprovado(cadastrar(cliente, descricao, risco=risco, comprovante=previa["comprovante"]), 201)
    assert registro["prioridade_sugerida"] == registro["prioridade_atual"] == nivel
    assert registro["rotulo_prioridade"] == rotulo
    assert registro["classificacao"]["prioridade"] == nivel
    assert registro["classificacao"]["justificativa"] == previa["justificativa"]
    assert registro["classificacao"]["alerta_seguranca"] is alerta


@pytest.mark.parametrize("com_comprovante", [True, False], ids=["com-previa", "cadastro-direto"])
def test_fio_de_poste_caido_em_patio_encabeca_fila(cliente, configuracao, com_comprovante):
    teclado = aprovado(cadastrar(cliente), 201)["id"]
    rede = aprovado(cadastrar(cliente, REDE), 201)["id"]
    descricao = "Fio do poste de alimentação elétrica, caido no chão próximo uma poça de água."
    dados = {**campos(descricao, risco=1), "servico_essencial_interrompido": 1, "pessoas_afetadas": 9}
    comprovante = {}
    if com_comprovante:
        previa = aprovado(enviar(cliente, "/api/classificar", dados), 200)
        assert previa["prioridade"] == 2
        assert previa["rotulo"] == "Prioritário"
        assert previa["alerta_seguranca"]
        assert previa["revisao_necessaria"]
        comprovante["comprovante"] = previa["comprovante"]

    registro = aprovado(enviar(cliente, "/api/chamados", {
        **dados, **comprovante, "local": "Pátio escolar", "confirmado": True, "equipe_confirmada": "Elétrica",
    }), 201)
    assert registro["prioridade_sugerida"] == registro["prioridade_atual"] == 2
    assert registro["rotulo_prioridade"] == "Prioritário"
    assert registro["classificacao"]["alerta_seguranca"]

    persistente = aplicacao.create_app(configuracao).test_client()
    fila = listar(persistente)
    assert ids(fila) == [registro["id"], rede, teclado]
    assert fila["contagens"] == {"0": 1, "1": 1, "2": 1}
    assert fila["chamados"][0]["classificacao"]["alerta_seguranca"]


def test_comprovante_anterior_a_correcao_forca_nova_triagem(configuracao):
    chave = "chave-ficticia-de-assinatura"
    cliente = aplicacao.create_app({**configuracao, "PRIORIZA_CHAVE_ASSINATURA": chave}).test_client()
    anterior = URLSafeTimedSerializer(chave, salt="prioriza-triagem-v1",
                                      signer_kwargs={"digest_method": aplicacao.hashlib.sha256})
    descricao = "Fio caído do poste perto do portão da escola."
    comprovante = anterior.dumps({
        "entrada": aplicacao.digest_triagem(descricao, campos(descricao), None),
        "classificacao": {"prioridade": 0},
    })
    registro = aprovado(cadastrar(cliente, descricao, comprovante=comprovante), 201)
    assert registro["prioridade_atual"] == 2
    assert registro["classificacao"]["alerta_seguranca"]


@pytest.mark.parametrize("com_foto", [False, True], ids=["sem-foto", "com-foto"])
def test_comprovante_valido_reutiliza_a_decisao_sem_nova_analise(cliente, monkeypatch, com_foto):
    foto = jpeg("blue") if com_foto else None
    previa = aprovado(enviar(cliente, "/api/classificar", campos(FUMACA), foto), 200)

    def falhar(*args, **kwargs):
        pytest.fail("Comprovante válido deve reaproveitar a classificação da prévia.")

    monkeypatch.setattr(aplicacao, "classificar", falhar)
    registro = aprovado(cadastrar(cliente, FUMACA, foto=foto, comprovante=previa["comprovante"]), 201)
    assert registro["prioridade_atual"] == 2
    if com_foto:
        assert cliente.get(f"/api/chamados/{registro['id']}/foto").mimetype == "image/jpeg"


@pytest.mark.parametrize("alteracao", ["descricao", "campo", "foto", "assinatura"])
def test_comprovante_so_reaproveita_os_mesmos_dados_e_foto(cliente, monkeypatch, alteracao):
    chamada_original = aplicacao.classificar
    chamadas = []

    def observar(descricao, atributos, foto=None, **config):
        chamadas.append((descricao, dict(atributos), foto))
        return chamada_original(descricao, atributos, foto, **config)

    monkeypatch.setattr(aplicacao, "classificar", observar)
    foto = jpeg("blue")
    previa = aprovado(enviar(cliente, "/api/classificar", campos(TECLADO), foto), 200)
    opcoes = {"comprovante": previa["comprovante"]}
    descricao = TECLADO
    if alteracao == "descricao":
        descricao = FUMACA
    elif alteracao == "campo":
        opcoes["pessoas_afetadas"] = 4
    elif alteracao == "foto":
        foto = jpeg("red")
    else:
        opcoes["comprovante"] += "assinatura-alterada"

    registro = aprovado(cadastrar(cliente, descricao, foto=foto, **opcoes), 201)
    assert len(chamadas) == 2
    assert registro["prioridade_atual"] == (2 if alteracao == "descricao" else 0)
    assert registro["foto_url"]


def test_dados_invalidos_e_classificacao_inventada_nao_sao_aceitos(cliente):
    for invalidos in ({"descricao": " "}, {"risco_seguranca": True}, {"pessoas_afetadas": -1}):
        assert enviar(cliente, "/api/classificar", {**campos(), **invalidos}).status_code == 400
    assert enviar(cliente, "/api/classificar", campos(), foto=b"arquivo falso").status_code == 400
    for inventado in ({"prioridade_atual": 0}, {"prioridade_sugerida": 0}, {"classificacao": {"prioridade": 0}}):
        assert cadastrar(cliente, FUMACA, **inventado).status_code == 400
    assert listar(cliente)["total"] == 0


def test_fila_ordenada_repriorizacao_conclusao_e_historico(cliente, configuracao):
    primeiro = aprovado(cadastrar(cliente), 201)["id"]
    segundo = aprovado(cadastrar(cliente, ETIQUETA), 201)["id"]
    intermediario = aprovado(cadastrar(cliente, REDE), 201)["id"]
    prioritario = aprovado(cadastrar(cliente, FUMACA), 201)["id"]

    # A ordem dos IDs e a ordem cronológica divergem entre os dois primeiros.
    with sqlite3.connect(configuracao["DATABASE_PATH"]) as conexao:
        conexao.execute("UPDATE chamados SET data_abertura = ? WHERE id = ?", ("2020-01-01T10:00:00+00:00", segundo))

    pendentes = listar(cliente)
    assert ids(pendentes) == [prioritario, intermediario, segundo, primeiro]
    assert pendentes["contagens"] == {"0": 2, "1": 1, "2": 1}

    alterado = aprovado(
        editar(cliente, primeiro, prioridade_atual=2, motivo="Impacto confirmado pela manutenção"), 200
    )
    assert alterado["prioridade_sugerida"] == 0
    assert alterado["prioridade_atual"] == 2
    assert alterado["classificacao"]["prioridade"] == 0
    assert ids(listar(cliente)) == [primeiro, prioritario, intermediario, segundo]
    assert ids(listar(cliente, prioridade=2, equipe="TI", status="Aberto")) == [primeiro, prioritario]

    aprovado(editar(cliente, primeiro, status="Em atendimento"), 200)
    assert ids(listar(cliente)) == [primeiro, prioritario, intermediario, segundo]
    assert ids(listar(cliente, status="Em atendimento")) == [primeiro]
    aprovado(editar(cliente, primeiro, status="Resolvido"), 200)
    assert ids(listar(cliente)) == [prioritario, intermediario, segundo]
    assert listar(cliente)["contagens"] == {"0": 1, "1": 1, "2": 1}
    assert ids(listar(cliente, visao="historico")) == [primeiro]
    assert set(ids(listar(cliente, visao="todos"))) == {primeiro, prioritario, intermediario, segundo}

    persistente = aplicacao.create_app(configuracao).test_client()
    assert ids(listar(persistente)) == [prioritario, intermediario, segundo]
    detalhe = aprovado(persistente.get(f"/api/chamados/{primeiro}"), 200)
    assert detalhe["status"] == "Resolvido"
    alteracoes = detalhe["historico_alteracoes"]
    assert len(alteracoes) == 3
    assert all(item["responsavel"] == configuracao["PRIORIZA_ADMIN_NOME"] for item in alteracoes)
    prioridade = next(item for item in alteracoes if "prioridade_atual" in item["novo"])
    assert prioridade["anterior"]["prioridade_atual"] == 0
    assert prioridade["novo"]["prioridade_atual"] == 2
    assert prioridade["motivo"] == "Impacto confirmado pela manutenção"


def test_aberturas_simultaneas_desempatam_por_id(configuracao, monkeypatch):
    class RelogioFixo(datetime):
        @classmethod
        def now(cls, tz=None):
            instante = datetime(2021, 1, 1, 10, tzinfo=timezone.utc)
            return instante.astimezone(tz) if tz else instante.replace(tzinfo=None)

    monkeypatch.setattr(aplicacao, "datetime", RelogioFixo)
    app = aplicacao.create_app(configuracao)

    def criar(_):
        with app.test_client() as cliente:
            return aprovado(cadastrar(cliente), 201)

    with ThreadPoolExecutor(max_workers=2) as executor:
        registros = list(executor.map(criar, range(2)))

    assert len({r["data_abertura"] for r in registros}) == 1
    assert ids(listar(app.test_client())) == sorted(r["id"] for r in registros)


def test_autorizacao_e_justificativa_de_revisao(cliente, configuracao):
    registro = aprovado(cadastrar(cliente, FUMACA), 201)
    id_chamado = registro["id"]
    rota = f"/api/chamados/{id_chamado}"
    for headers in ({}, {"Authorization": "Bearer incorreto"}):
        assert cliente.patch(rota, json={"status": "Resolvido"}, headers=headers).status_code == 401

    sem_admin = aplicacao.create_app({**configuracao, "PRIORIZA_ADMIN_TOKEN": ""}).test_client()
    assert sem_admin.patch(rota, json={"status": "Resolvido"}, headers=AUTORIZACAO).status_code == 403

    assert editar(cliente, id_chamado, prioridade_atual=0).status_code == 400
    assert editar(cliente, id_chamado, prioridade_atual=0, motivo="   ").status_code == 400
    assert editar(cliente, id_chamado, prioridade_atual=True, motivo="Valor inválido").status_code == 400
    assert editar(cliente, id_chamado, prioridade_sugerida=0, motivo="Tentativa de sobrescrever a IA").status_code == 400
    assert editar(cliente, id_chamado, status="Resolvido", responsavel="Identidade enviada pelo cliente").status_code == 400

    detalhe = aprovado(cliente.get(rota), 200)
    assert detalhe["status"] == "Aberto"
    assert detalhe["prioridade_atual"] == detalhe["prioridade_sugerida"] == 2
    assert detalhe["historico_alteracoes"] == []


def test_migracao_preserva_chamados_binarios_fotos_e_historico(configuracao):
    # Reproduz o esquema anterior, no qual o CHECK permitia apenas 0 e 1.
    caminho = configuracao["DATABASE_PATH"]
    with sqlite3.connect(caminho) as conexao:
        conexao.executescript("""
            CREATE TABLE chamados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL, local TEXT NOT NULL, data_abertura TEXT NOT NULL,
                risco_seguranca INTEGER NOT NULL, servico_essencial_interrompido INTEGER NOT NULL,
                pessoas_afetadas INTEGER NOT NULL, dias_aguardando INTEGER NOT NULL,
                recorrente INTEGER NOT NULL, prioridade_sugerida INTEGER NOT NULL
                    CHECK(prioridade_sugerida IN (0, 1)),
                equipe_sugerida TEXT NOT NULL, justificativa_equipe TEXT NOT NULL,
                equipe_confirmada TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aberto',
                foto_caminho TEXT, analise_json TEXT
            );
        """)
        for nivel, status, foto in [(0, "Resolvido", None), (1, "Aberto", "uploads/legada.jpg")]:
            conexao.execute(
                """INSERT INTO chamados VALUES (NULL, ?, 'Sala', ?, 0, 0, 0, 0, 0, ?,
                   'TI', 'Motivo anterior', 'TI', ?, ?, NULL)""",
                (TECLADO, "2020-01-01T10:00:00+00:00", nivel, status, foto),
            )

    pasta_fotos = Path(configuracao["UPLOAD_FOLDER"])
    pasta_fotos.mkdir()
    original = jpeg("blue")
    (pasta_fotos / "legada.jpg").write_bytes(original)

    for _ in range(2):
        cliente = aplicacao.create_app(configuracao).test_client()
        pendente, = listar(cliente)["chamados"]
        concluido, = listar(cliente, visao="historico")["chamados"]
        assert pendente["id"] == 2 and pendente["prioridade_sugerida"] == pendente["prioridade_atual"] == 2
        assert concluido["id"] == 1 and concluido["prioridade_sugerida"] == concluido["prioridade_atual"] == 0
        assert pendente["classificacao"] is None
        assert cliente.get("/api/chamados/2/foto").data == original
