"""Integração de extração testada com respostas simuladas, sem consumir API real."""
import json
from unittest.mock import Mock, patch

import pytest
import requests

from app import FEATURES, create_app


@pytest.fixture
def client():
    # Chave fictícia; todas as saídas de rede deste módulo são interceptadas.
    return create_app({"TESTING": True, "OPENAI_API_KEY": "chave-ficticia-de-teste"}).test_client()


def resposta_mock(campos):
    resposta = Mock()
    resposta.json.return_value = {"choices": [{"message": {"content": json.dumps(campos)}}]}
    return resposta


def test_extraicao_preserva_desconhecidos_e_exige_confirmacao(client):
    campos = dict.fromkeys(FEATURES, None)
    campos["risco_seguranca"] = 1
    with patch("app.requests.post", return_value=resposta_mock(campos)) as post:
        resposta = client.post("/api/extrair", json={"descricao": "Fiação exposta em local de pouca circulação."})
    assert resposta.status_code == 200
    assert resposta.json["campos"] == campos
    assert resposta.json["confirmacao_necessaria"] is True
    assert "não confirmadas" in resposta.json["origem"]
    argumentos = post.call_args.kwargs
    assert argumentos["timeout"] == (5, 25)
    assert argumentos["json"]["response_format"]["json_schema"]["strict"] is True
    assert "null" in argumentos["json"]["messages"][0]["content"]


def test_config_extracao_habilitada(client):
    assert client.get("/config.json").json["extracao_habilitada"] is True


def test_sem_chave_nao_faz_chamada():
    client = create_app({"TESTING": True, "OPENAI_API_KEY": ""}).test_client()
    with patch("app.requests.post") as post:
        resposta = client.post("/api/extrair", json={"descricao": "Falta de água."})
    assert resposta.status_code == 503
    post.assert_not_called()


@pytest.mark.parametrize("payload", [{}, {"descricao": ""}, {"descricao": "  "},
    {"descricao": None}, {"descricao": 5}, {"descricao": "x" * 2001},
    {"descricao": "Falta água", "prioridade": 1}, [], None])
def test_descricao_invalida_nao_sai_para_provedor(client, payload):
    with patch("app.requests.post") as post:
        resposta = client.post("/api/extrair", data=json.dumps(payload), content_type="application/json")
    assert resposta.status_code == 400
    post.assert_not_called()


@pytest.mark.parametrize("erro", [requests.Timeout("simulado"), requests.HTTPError("simulado")])
def test_falha_externa_preserva_entrada_manual(client, erro):
    with patch("app.requests.post", side_effect=erro):
        resposta = client.post("/api/extrair", json={"descricao": "Chamado fictício."})
    assert resposta.status_code == 502
    assert "manualmente" in resposta.json["erro"]
    assert "chave-ficticia" not in resposta.get_data(as_text=True)


@pytest.mark.parametrize("campos", [dict.fromkeys(FEATURES, "desconhecido"),
    dict.fromkeys(FEATURES, True), {}, {**dict.fromkeys(FEATURES, None), "prioridade": 1},
    {**dict.fromkeys(FEATURES, None), "risco_seguranca": 2}])
def test_resposta_malformada_nao_e_aceita(client, campos):
    with patch("app.requests.post", return_value=resposta_mock(campos)):
        resposta = client.post("/api/extrair", json={"descricao": "Chamado fictício."})
    assert resposta.status_code == 502


def test_provedor_sem_content_nao_expoe_resposta(client):
    resposta_provedor = Mock()
    resposta_provedor.json.return_value = {"choices": []}
    with patch("app.requests.post", return_value=resposta_provedor):
        resposta = client.post("/api/extrair", json={"descricao": "Chamado fictício."})
    assert resposta.status_code == 502
