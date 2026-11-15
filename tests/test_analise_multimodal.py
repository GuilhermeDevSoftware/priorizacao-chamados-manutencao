"""Contrato multimodal com provedor simulado; nenhuma chamada real à OpenAI."""
import io
import json
from unittest.mock import Mock, patch

import pytest
import requests

from app import FEATURES, create_app
from test_chamados import foto_sintetica, dados, cadastrar


@pytest.fixture
def client(tmp_path):
    return create_app({"TESTING": True, "OPENAI_API_KEY": "chave-ficticia-de-teste",
        "DATABASE_PATH": str(tmp_path/"chamados.sqlite3"), "UPLOAD_FOLDER": str(tmp_path/"uploads")}).test_client()


def analise():
    campos = dict.fromkeys(FEATURES, None)
    campos["risco_seguranca"] = 1
    return {"tipo_defeito": "Possível fiação exposta", "indicios_observados": ["Material condutor aparente na imagem sintética"],
            "areas_identificadas": ["Elétrica"], "ambiguo": False, "equipe_sugerida": "Elétrica",
            "justificativa_equipe": "Os indícios são de instalação elétrica.", "campos": campos,
            "informacoes_confirmar": ["Confirmar risco, pessoas afetadas, espera e recorrência."]}


def resposta_provedor(conteudo):
    resposta = Mock()
    resposta.json.return_value = {"choices": [{"message": {"content": json.dumps(conteudo)}}]}
    return resposta


def solicitar_analise(client, **kwargs):
    kwargs.setdefault("content_type", "multipart/form-data")
    return client.post("/api/analisar", **kwargs)


def test_foto_e_descricao_enviadas_ao_provedor_com_esquema(client):
    with patch("app.requests.post", return_value=resposta_provedor(analise())) as externa:
        resposta = solicitar_analise(client, data={"descricao": "Fiação exposta — exemplo fictício.",
            "foto": (io.BytesIO(foto_sintetica()), "fiacao.jpg")}, content_type="multipart/form-data")
    assert resposta.status_code == 200, resposta.json
    assert resposta.json["origem"] == "ia_multimodal"
    assert resposta.json["confirmacao_necessaria"] is True
    assert resposta.json["equipe_sugerida"] == "Elétrica"
    assert resposta.json["campos"]["pessoas_afetadas"] is None
    assert client.get("/api/chamados").json["total"] == 0
    parametros = externa.call_args.kwargs
    assert parametros["json"]["response_format"]["json_schema"]["strict"] is True
    conteudo = parametros["json"]["messages"][-1]["content"]
    assert isinstance(conteudo, list)
    assert any(x.get("type") == "text" and "Fiação" in x["text"] for x in conteudo)
    assert any(x.get("type") == "image_url" and x["image_url"]["url"].startswith("data:image/jpeg;base64,") for x in conteudo)


def test_analise_so_descricao_e_armazenamento_da_sugestao(client):
    with patch("app.requests.post", return_value=resposta_provedor(analise())):
        resposta = solicitar_analise(client, data={"descricao": "Fiação exposta em sala fictícia."})
    assert resposta.status_code == 200
    corpo = dados("Fiação exposta em sala fictícia.", "Triagem geral", risco=1)
    corpo["analise"] = resposta.json
    with patch("app.requests.post") as externa:
        salvo = cadastrar(client, corpo)
    externa.assert_not_called()
    assert salvo.status_code == 201, salvo.json
    assert salvo.json["equipe_sugerida"] == "Elétrica"
    assert salvo.json["equipe_confirmada"] == "Triagem geral"
    assert salvo.json["analise"]["indicios_observados"]


@pytest.mark.parametrize("areas,ambiguo", [(["TI", "Elétrica"], False), (["Elétrica"], True), ([], False)])
def test_varias_areas_ou_incerteza_encaminham_triagem(client, areas, ambiguo):
    sugestao = analise(); sugestao["areas_identificadas"] = areas; sugestao["ambiguo"] = ambiguo
    with patch("app.requests.post", return_value=resposta_provedor(sugestao)):
        resposta = solicitar_analise(client, data={"descricao": "Problema fictício que precisa de confirmação."})
    assert resposta.status_code == 200, resposta.json
    assert resposta.json["equipe_sugerida"] == "Triagem geral"


@pytest.mark.parametrize("falha", [requests.Timeout("simulado"), requests.HTTPError("simulado"), ValueError("JSON inválido simulado")])
def test_indisponibilidade_da_ia_mantem_fallback_e_cadastro(client, falha):
    with patch("app.requests.post", side_effect=falha):
        resposta = solicitar_analise(client, data={"descricao": "Vazamento na torneira fictícia."})
    assert resposta.status_code == 200
    assert resposta.json["origem"] == "regra_local"
    assert resposta.json["aviso"]
    assert resposta.json["equipe_sugerida"] == "Hidráulica"
    assert all(v is None for v in resposta.json["campos"].values())
    assert cadastrar(client).status_code == 201


@pytest.mark.parametrize("malformado", [{}, {"campos": {}}, {**analise(), "campos": dict.fromkeys(FEATURES, True)},
    {**analise(), "areas_identificadas": ["Engenharia espacial"]}])
def test_resposta_malformada_nao_preenche_campos(client, malformado):
    with patch("app.requests.post", return_value=resposta_provedor(malformado)):
        resposta = solicitar_analise(client, data={"descricao": "Impressora com defeito — cenário fictício."})
    assert resposta.status_code == 200
    assert resposta.json["origem"] == "regra_local"
    assert all(v is None for v in resposta.json["campos"].values())


def test_imagem_invalida_nao_e_enviada_ao_provedor(client):
    with patch("app.requests.post") as externa:
        resposta = solicitar_analise(client, data={"descricao": "Imagem fictícia inválida.", "foto": (io.BytesIO(b"arquivo falso"), "foto.jpg")})
    assert resposta.status_code == 400
    externa.assert_not_called()


@pytest.mark.parametrize("descricao", ["", "  ", "x"*2001])
def test_analise_sem_descricao_valida(client, descricao):
    with patch("app.requests.post") as externa:
        resposta = solicitar_analise(client, data={"descricao": descricao})
    assert resposta.status_code == 400
    externa.assert_not_called()


def test_sem_chave_sugere_equipe_sem_fingir_visao(tmp_path):
    client = create_app({"TESTING": True, "OPENAI_API_KEY": "", "DATABASE_PATH": str(tmp_path/"chamados.sqlite3"),
                         "UPLOAD_FOLDER": str(tmp_path/"uploads")}).test_client()
    with patch("app.requests.post") as externa:
        resposta = solicitar_analise(client, data={"descricao": "Computador com defeito.",
            "foto": (io.BytesIO(foto_sintetica()), "fiacao-sintetica.jpg")})
    externa.assert_not_called()
    assert resposta.status_code == 200
    assert resposta.json["origem"] == "regra_local"
    assert resposta.json["equipe_sugerida"] == "TI"
    assert resposta.json["indicios_observados"] == []
    assert resposta.json["aviso"]
