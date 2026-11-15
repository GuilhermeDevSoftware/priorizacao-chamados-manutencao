"""Testes medidos de contrato HTTP e validação, com um artefato de teste isolado."""
import json

import pytest

from app import FEATURES, MAX_INTEIRO, create_app


@pytest.fixture
def client(tmp_path):
    arvore = {
        "feature_order": FEATURES,
        "classes": [0, 1],
        "nodes": [
            {"id": 0, "feature_index": 0, "threshold": 0.5, "left": 1, "right": 2, "prediction": 0},
            {"id": 1, "feature_index": -2, "threshold": -2, "left": -1, "right": -1, "prediction": 0},
            {"id": 2, "feature_index": -2, "threshold": -2, "left": -1, "right": -1, "prediction": 1},
        ],
    }
    caminho = tmp_path / "arvore.json"
    caminho.write_text(json.dumps(arvore), encoding="utf-8")
    return create_app({"TESTING": True, "MODEL_PATH": str(caminho), "OPENAI_API_KEY": ""}).test_client()


@pytest.fixture
def chamado():
    return dict(zip(FEATURES, [0, 0, 0, 2, 0]))


def test_previsao_normal_com_resumo(client, chamado):
    chamado["descricao"] = "Maçaneta frouxa em sala desocupada."
    resposta = client.post("/api/prever", json=chamado)
    assert resposta.status_code == 200
    assert resposta.json == {"classe": 0, "rotulo": "Normal", "campos": chamado}
    assert resposta.headers["Cache-Control"] == "no-store"


def test_previsao_prioritaria_com_risco(client, chamado):
    chamado["risco_seguranca"] = 1
    resposta = client.post("/api/prever", json=chamado)
    assert resposta.status_code == 200
    assert resposta.json["classe"] == 1
    assert resposta.json["rotulo"] == "Prioritário"


@pytest.mark.parametrize("campo,valor", [
    ("risco_seguranca", 2), ("risco_seguranca", True),
    ("servico_essencial_interrompido", -1), ("recorrente", "1"),
    ("pessoas_afetadas", -1), ("pessoas_afetadas", 1.5),
    ("pessoas_afetadas", False), ("dias_aguardando", None),
    ("dias_aguardando", MAX_INTEIRO + 1),
])
def test_valores_invalidos_nao_sao_convertidos(client, chamado, campo, valor):
    chamado[campo] = valor
    resposta = client.post("/api/prever", json=chamado)
    assert resposta.status_code == 400
    assert campo in resposta.json["detalhes"]


@pytest.mark.parametrize("corpo", [{}, [], None, "texto", {"prioridade": 1}])
def test_formulario_incompleto_ou_corpo_invalido(client, corpo):
    resposta = client.post("/api/prever", data=json.dumps(corpo), content_type="application/json")
    assert resposta.status_code == 400
    assert "erro" in resposta.json


def test_campo_extra_impede_ambiguidade(client, chamado):
    chamado["prioridade"] = 1
    assert client.post("/api/prever", json=chamado).status_code == 400


@pytest.mark.parametrize("descricao", [None, 2, "x" * 2001])
def test_descricao_invalida(client, chamado, descricao):
    chamado["descricao"] = descricao
    assert client.post("/api/prever", json=chamado).status_code == 400


def test_limite_inteiro_aceito_sem_perder_contrato(client, chamado):
    chamado["pessoas_afetadas"] = MAX_INTEIRO
    assert client.post("/api/prever", json=chamado).status_code == 200


def test_content_type_e_json_malformado(client):
    assert client.post("/api/prever", data="{}").status_code == 415
    resposta = client.post("/api/prever", data="{", content_type="application/json")
    assert resposta.status_code == 400
    assert resposta.json["erro"].startswith("O corpo")


def test_configuracao_e_artefato(client):
    assert client.get("/config.json").json == {"modo": "api", "extracao_habilitada": False}
    assert client.get("/modelo/arvore.json").json["feature_order"] == FEATURES


def test_modelo_ausente_informa_indisponibilidade(tmp_path, chamado):
    app = create_app({"TESTING": True, "MODEL_PATH": str(tmp_path / "ausente.json"), "OPENAI_API_KEY": ""})
    resposta = app.test_client().post("/api/prever", json=chamado)
    assert resposta.status_code == 503
    assert "modelo" in resposta.json["erro"]


def test_corpo_muito_grande(client):
    resposta = client.post("/api/prever", data=" " * 33000, content_type="application/json")
    assert resposta.status_code == 413
