"""Fronteiras inteiras e separação entre consistência sintética e validação."""
import joblib
import numpy as np

from scripts.ml_comum import ROOT, FEATURES, politica
from scripts.interpretar_arvore import comparar_limiares, verificar_celulas
from scripts.analisar_fronteiras import gerar_grade, resumir_erros


def test_grade_cobre_produto_cartesiano_sem_duplicatas():
    grade = gerar_grade()
    assert len(grade) == 800
    assert not grade[FEATURES].duplicated().any()
    assert set(grade.pessoas_afetadas) == {*range(8, 13), *range(38, 43)}
    assert set(grade.dias_aguardando) == {*range(5, 10), *range(12, 17)}
    assert np.array_equal(grade.prioridade_politica, politica(grade[FEATURES]))


def test_arvore_publicada_recupera_fronteiras_inteiras():
    arvore = joblib.load(ROOT / "modelo/arvore.joblib")
    cortes = comparar_limiares(arvore)
    assert all(c["equivalente_em_inteiros"] for c in cortes)
    assert {c["limiar_politica_correspondente"] for c in cortes} == {1, 7, 10, 14, 40}
    assert verificar_celulas(arvore)["divergencias"] == 0
    grade = gerar_grade()
    assert np.array_equal(arvore.predict(grade[FEATURES]), grade.prioridade_politica)


def test_taxa_falso_negativo_usa_positivos_como_denominador():
    resultado = resumir_erros([0, 1, 1, 0], [1, 0, 1, 0])
    assert resultado["falsos_negativos"] == resultado["falsos_positivos"] == 1
    assert resultado["taxa_falsos_negativos"] == .5
    assert resumir_erros([0, 0], [0, 1])["taxa_falsos_negativos"] is None
