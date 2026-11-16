"""Testa o protocolo estatístico, o baseline forte e a separação por famílias."""
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.ml_comum import ROOT, FEATURES, carregar_dados, criar_modelos, divisao_original, metricas, politica
from scripts.avaliar_modelos import bootstrap_familias, executar, metricas_contagens


def test_politica_reproduz_rotulos_e_baseline_nao_aprende_ruido():
    base = carregar_dados()
    assert np.array_equal(politica(base), base.prioridade)
    regras = criar_modelos()["Regras"]
    regras.fit(base[FEATURES], 1 - base.prioridade)
    assert np.array_equal(regras.predict(base[FEATURES]), base.prioridade)


def test_divisao_original_preserva_ids_e_familias():
    base = carregar_dados()
    treino, teste = divisao_original(base)
    declarada = pd.read_csv(ROOT / "dados/divisao_treino_teste.csv")
    assert len(treino) == 96 and len(teste) == 24
    assert set(base.iloc[teste].id) == set(declarada.loc[declarada.conjunto == "teste", "id"])
    assert not set(base.iloc[treino].familia_cenario) & set(base.iloc[teste].familia_cenario)


def test_metricas_vetorizadas_correspondem_ao_sklearn():
    y, p = [0, 0, 1, 1, 1], [0, 1, 0, 1, 1]
    medidas = metricas_contagens(np.array([1, 1, 1, 2]))
    for nome, valor in metricas(y, p).items():
        assert float(medidas[nome]) == pytest.approx(valor)


def test_bootstrap_cluster_deterministico_nao_trata_repeticoes_como_novos_dados():
    y = np.array([0, 0, 1, 1]); p = np.array([[0, 1, 1, 0]])
    grupos = np.array(["a", "a", "b", "b"])
    a = bootstrap_familias(y, p, grupos, amostras=100)
    b = bootstrap_familias(y, np.repeat(p, 10, axis=0), grupos, amostras=100)
    for nome in a:
        assert a[nome] == pytest.approx(b[nome])
    assert a == bootstrap_familias(y, p, grupos, amostras=100)


def test_avaliacao_gera_saidas_isola_reservado_e_nao_modifica_modelo(tmp_path):
    protegido = (ROOT / "modelo/arvore.json").read_bytes()
    (tmp_path / "dados").mkdir()
    (tmp_path / "modelo").mkdir()
    shutil.copy2(ROOT / "dados/chamados_ficticios.csv", tmp_path / "dados/chamados_ficticios.csv")
    shutil.copy2(ROOT / "modelo/arvore.joblib", tmp_path / "modelo/arvore.joblib")
    resultado = executar(raiz=tmp_path, repeticoes=2, bootstrap=20)
    assert resultado["protocolo"]["repeticoes"] == 2
    assert len(resultado["por_fold"]) == 2 * 5 * 5
    base = carregar_dados()
    _, idx = divisao_original(base)
    reservadas = set(base.iloc[idx].familia_cenario)
    assinaturas = {}
    for fold in resultado["particoes_familias"]:
        assinaturas.setdefault(fold["seed"], []).append(tuple(fold["familias_validacao"]))
        assert not set(fold["familias_treino"]) & set(fold["familias_validacao"])
        assert not reservadas & (set(fold["familias_treino"]) | set(fold["familias_validacao"]))
    assert len(set(tuple(sorted(x)) for x in assinaturas.values())) == 2
    for nome, medidas in resultado["modelos"].items():
        for metrica, valor in medidas["validacao_cruzada"].items():
            lo, hi = valor["ic95_bootstrap_familias"]
            assert 0 <= lo <= hi <= 1
            assert 0 <= valor["media"] <= 1
    assert resultado["modelos"]["Regras"]["validacao_cruzada"]["f2"]["media"] == 1
    assert (ROOT / "modelo/arvore.json").read_bytes() == protegido
    pasta = tmp_path / "relatorios"
    assert json.loads((pasta / "comparacao_modelos.json").read_text())["protocolo"]["bootstrap"]["unidade"] == "família inteira"
    oof = pd.read_csv(pasta / "predicoes_oof_modelos.csv")
    assert len(oof) == 96 * 2
    assert not set(oof.id) & set(base.iloc[idx].id)
    assert (pasta / "comparacao_modelos.md").is_file()
