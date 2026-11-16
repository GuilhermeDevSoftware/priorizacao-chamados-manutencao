"""Contrato de reprodução e isolamento do notebook acadêmico."""
from io import BytesIO
import re
from zipfile import ZipFile

import nbformat

from scripts.montar_notebook import ARQUIVOS, ROOT, montar, pacote_embutido


def test_pacote_embute_fontes_e_dados_sem_estado_local_ou_relatorios():
    dados, manifesto = pacote_embutido()
    assert pacote_embutido()[0] == dados
    with ZipFile(BytesIO(dados)) as pacote:
        assert set(pacote.namelist()) == set(ARQUIVOS) == set(manifesto)
        for nome in pacote.namelist():
            assert not nome.startswith("/") and ".." not in nome.split("/")
            assert not set(nome.split("/")) & {"instance", "uploads", "relatorios", ".env"}
        assert pacote.read("modelo/arvore.json") == (ROOT / "modelo/arvore.json").read_bytes()
        assert pacote.read("modelo/arvore.joblib") == (ROOT / "modelo/arvore.joblib").read_bytes()


def test_notebook_autocontido_exige_isolamento_e_experimentos_completos():
    notebook, _ = montar()
    codigos = [c.source for c in notebook.cells if c.cell_type == "code"]
    fonte = "\n".join(codigos)
    assert "TemporaryDirectory" in fonte and "RAIZ_EXP" in fonte
    assert "relatorios_precalculados" not in fonte
    assert 'AMBIENTE["OPENAI_API_KEY"] = ""' in fonte
    for script in ("avaliar_modelos.py", "interpretar_arvore.py", "analisar_fronteiras.py", "experimento_ruido.py", "curva_aprendizado.py", "treinar_texto.py"):
        assert f'executar_script("{script}")' in fonte
    assert len(set(c.id for c in notebook.cells)) == len(notebook.cells)


def test_notebook_tem_secoes_pedagogicas_e_nao_insere_datas():
    notebook, _ = montar()
    texto = "\n".join(c.source for c in notebook.cells if c.cell_type == "markdown")
    for tema in ("Baselines", "interpretabilidade", "Fronteiras", "ruído", "aprendizado", "Classificador de texto", "Ameaças à validade"):
        assert tema.casefold() in texto.casefold()
    assert not re.search(r"\b\d{2}/\d{2}/\d{4}\b|\b20\d{2}-\d{2}-\d{2}\b", texto)
    assert "Guilherme Costa" in texto


def test_notebook_entregue_tem_saidas_e_corresponde_as_fontes_atuais():
    notebook = nbformat.read(ROOT / "Projeto_Chamados_Manutencao.ipynb", as_version=4)
    codigos = [c for c in notebook.cells if c.cell_type == "code"]
    assert codigos and all(c.execution_count is not None for c in codigos)
    assert not [o for c in codigos for o in c.outputs if o.output_type == "error"]
    assert notebook.metadata["projeto"]["fontes_sha256"] == pacote_embutido()[1]
