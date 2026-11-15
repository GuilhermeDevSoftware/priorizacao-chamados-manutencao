"""Compara as três implementações reais; a referência é o scikit-learn."""
from __future__ import annotations

import itertools
import json
from pathlib import Path
import subprocess

import joblib
import numpy as np
import pandas as pd

from app import create_app

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["risco_seguranca", "servico_essencial_interrompido", "pessoas_afetadas", "dias_aguardando", "recorrente"]


def casos_de_paridade():
    """Base inteira, grade de fronteiras aprendidas e amostra independente seed 42."""
    modelo_json = json.loads((ROOT / "modelo/arvore.json").read_text(encoding="utf-8"))
    base = pd.read_csv(ROOT / "dados/chamados_ficticios.csv")
    casos = base[FEATURES].to_dict(orient="records")
    valores = {2: {0, 1, 19, 20, 21, 49, 50, 51, 99, 100, 101, 1000},
               3: {0, 1, 6, 7, 8, 13, 14, 15, 29, 30, 31, 1000}}
    for no in modelo_json["nodes"]:
        indice = no["feature_index"]
        if indice in valores:
            limite = no["threshold"]
            valores[indice].update(max(0, int(v)) for v in [np.floor(limite) - 1, np.floor(limite), np.ceil(limite), np.ceil(limite) + 1])
    for risco, essencial, pessoas, dias, recorrente in itertools.product(
        (0, 1), (0, 1), sorted(valores[2]), sorted(valores[3]), (0, 1)
    ):
        casos.append(dict(zip(FEATURES, [risco, essencial, pessoas, dias, recorrente])))
    gerador = np.random.default_rng(42)
    for _ in range(256):
        casos.append(dict(zip(FEATURES, [int(gerador.integers(0, 2)), int(gerador.integers(0, 2)),
                                       int(gerador.integers(0, 501)), int(gerador.integers(0, 121)),
                                       int(gerador.integers(0, 2))])))
    # Limite de inteiro aceito por Flask e JavaScript.
    for risco, essencial, recorrente in itertools.product((0, 1), repeat=3):
        casos.append(dict(zip(FEATURES, [risco, essencial, 9007199254740991, 9007199254740991, recorrente])))
    return casos


def medir_paridade():
    casos = casos_de_paridade()
    modelo = joblib.load(ROOT / "modelo/arvore.joblib")
    referencia = modelo.predict(pd.DataFrame(casos, columns=FEATURES)).astype(int).tolist()
    aplicacao = create_app({"TESTING": True, "OPENAI_API_KEY": ""})
    flask_previsoes = []
    with aplicacao.test_client() as cliente:
        for indice, campos in enumerate(casos):
            resposta = cliente.post("/api/prever", json=campos)
            assert resposta.status_code == 200, (indice, resposta.get_json())
            flask_previsoes.append(resposta.get_json()["classe"])
    resultado = subprocess.run(
        ["node", str(ROOT / "tests/paridade.mjs")],
        input=json.dumps({"modelo": str(ROOT / "modelo/arvore.json"), "casos": casos}),
        text=True, capture_output=True, check=True, cwd=ROOT,
    )
    javascript = json.loads(resultado.stdout)
    assert len(referencia) == len(flask_previsoes) == len(javascript)
    divergencias = [i for i, trio in enumerate(zip(referencia, flask_previsoes, javascript)) if len(set(trio)) != 1]
    assert not divergencias, f"Classes divergentes nos casos: {divergencias[:10]}"
    return {"casos": len(casos), "divergencias": len(divergencias), "implementacoes": ["scikit-learn", "Flask", "JavaScript/Node"], "semente": 42}


def test_paridade_sklearn_flask_javascript():
    assert medir_paridade()["divergencias"] == 0


def test_cenarios_obrigatorios():
    cenarios = [
        ("Maçaneta frouxa em sala desocupada", [0, 0, 0, 1, 0], 0),
        ("Falta de água na escola", [0, 1, 180, 0, 0], 1),
        ("Fiação exposta em local com pouca circulação", [1, 0, 1, 0, 0], 1),
    ]
    with create_app({"TESTING": True, "OPENAI_API_KEY": ""}).test_client() as cliente:
        for descricao, valores, classe in cenarios:
            resposta = cliente.post("/api/prever", json={**dict(zip(FEATURES, valores)), "descricao": descricao})
            assert resposta.status_code == 200
            assert resposta.get_json()["classe"] == classe, (descricao, resposta.get_json())
        incompleto = cliente.post("/api/prever", json={"risco_seguranca": 1})
        assert incompleto.status_code == 400
        assert "detalhes" in incompleto.get_json()
