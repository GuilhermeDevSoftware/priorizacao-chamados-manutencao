"""A curva mantém famílias inteiras e não consome o teste reservado."""
from pathlib import Path
import shutil

from scripts.curva_aprendizado import executar


def test_curva_agrupada_sem_vazamento_e_subconjuntos_aninhados(tmp_path):
    raiz = Path(__file__).resolve().parents[1]
    (tmp_path / "dados").mkdir()
    shutil.copy2(raiz / "dados/chamados_ficticios.csv", tmp_path / "dados/chamados_ficticios.csv")
    relatorio = executar(tmp_path, seeds=[42], tamanhos=[4, 8])
    reservado = set(relatorio["protocolo"]["ids_reservados_excluidos"])
    assert relatorio["protocolo"]["teste_reservado_usado"] is False
    assert relatorio["protocolo"]["quantidade_particoes"] == 5
    for particao in relatorio["particoes"]:
        val = set(particao["ids_validacao"])
        pequeno, grande = particao["subconjuntos"]
        assert set(pequeno["ids_treino"]) < set(grande["ids_treino"])
        assert not reservado & (val | set(grande["ids_treino"]))
        assert not val & set(grande["ids_treino"])
        assert len(pequeno["ids_treino"]) == 16
        assert len(grande["ids_treino"]) == 32
    assert len(relatorio["resultados"]) == 20
    assert (tmp_path / "relatorios/figuras/curva_aprendizado.png").is_file()
    assert (tmp_path / "relatorios/curva_aprendizado.json").is_file()
