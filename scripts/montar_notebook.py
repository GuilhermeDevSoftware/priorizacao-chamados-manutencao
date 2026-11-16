"""Monta e, opcionalmente, executa o notebook autocontido dos experimentos.

Uso: python scripts/montar_notebook.py --executar
As fontes e os dados são incorporados; a execução usa uma cópia temporária.
"""
from __future__ import annotations

import argparse
import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

import nbformat

ROOT = Path(__file__).resolve().parents[1]
ARQUIVOS = [
    "scripts/ml_comum.py", "scripts/avaliar_modelos.py",
    "scripts/interpretar_arvore.py", "scripts/analisar_fronteiras.py",
    "scripts/experimento_ruido.py", "scripts/curva_aprendizado.py",
    "scripts/treinar_texto.py", "texto_equipe.py", "multimodal.py", "storage.py",
    "dados/chamados_ficticios.csv", "dados/divisao_treino_teste.csv",
    "modelo/arvore.json", "modelo/arvore.joblib",
]
PROTEGIDOS = ["modelo/arvore.json", "modelo/arvore.joblib", "frontend/engine.js"]


def pacote_embutido(raiz=ROOT):
    raiz = Path(raiz)
    memoria = BytesIO()
    manifesto = {}
    with ZipFile(memoria, "w", ZIP_DEFLATED) as pacote:
        for nome in ARQUIVOS:
            dados = (raiz / nome).read_bytes()
            manifesto[nome] = sha256(dados).hexdigest()
            # Metadados fixos: não copiar horário de origem nem horário da sessão.
            entrada = ZipInfo(nome)
            entrada.compress_type = ZIP_DEFLATED
            entrada.external_attr = 0o600 << 16
            pacote.writestr(entrada, dados)
    return memoria.getvalue(), manifesto


def montar(raiz=ROOT):
    raiz = Path(raiz)
    pacote, manifesto = pacote_embutido(raiz)
    cells = []
    def md(texto):
        cells.append(nbformat.v4.new_markdown_cell(texto))
    def code(texto):
        cells.append(nbformat.v4.new_code_cell(texto.strip()))
    md("""# Sistema Inteligente para Priorização de Chamados de Manutenção

**Engenharia de Computação · Disciplina de Inteligência Artificial**

**Autor e único integrante: Guilherme Costa**

Todos os chamados são fictícios. O problema de prioridade foi construído a partir de uma política conhecida; por isso, o baseline de regras é uma referência mais forte que a classe majoritária. Neste cenário, não há justificativa operacional para substituir a política estável por ML. O objetivo dos modelos aprendidos é estudar avaliação por famílias, incerteza condicional, interpretabilidade, erros e robustez a ruído. O experimento de texto aborda uma tarefa distinta: sugerir equipe pela descrição.

Este notebook contém dados, árvore original e fontes dos experimentos. Não depende de upload manual nem de acesso ao repositório durante a execução. Nenhuma chamada à OpenAI é realizada. O Colab é compatível; as saídas entregues foram verificadas em kernel local limpo com `nbclient`.""")
    md("""## 1. Ambiente reproduzível e isolamento

As dependências têm versões fixadas. Somente a instalação de pacotes, quando necessária, exige internet. Os experimentos rodam em uma pasta temporária nova: não escrevem sobre o banco local, uploads ou árvore do aplicativo. Os resultados são regenerados a partir das fontes incorporadas, sem carregar relatórios previamente calculados.""")
    code("""import importlib.metadata as metadata
import subprocess
import sys
PACOTES = {"numpy": "2.3.5", "scipy": "1.17.0", "pandas": "2.2.3", "scikit-learn": "1.8.0", "joblib": "1.5.3", "matplotlib": "3.10.8", "Flask": "3.1.2", "requests": "2.34.2"}
instalar = []
for nome, versao in PACOTES.items():
    try:
        if metadata.version(nome) != versao:
            instalar.append(f"{nome}=={versao}")
    except metadata.PackageNotFoundError:
        instalar.append(f"{nome}=={versao}")
if instalar:
    subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *instalar], check=True)
print({nome: metadata.version(nome) for nome in PACOTES})""")
    code("ZIP_BASE64 = " + repr(base64.b64encode(pacote).decode("ascii")) + "\nMANIFESTO_FONTES = " + repr(manifesto) + "\n" + """import base64
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile
from zipfile import ZipFile
import pandas as pd
import numpy as np
from IPython.display import display, Image

PASTA_TEMPORARIA = tempfile.TemporaryDirectory(prefix="experimentos-chamados-")
RAIZ_EXP = Path(PASTA_TEMPORARIA.name)
with ZipFile(BytesIO(base64.b64decode(ZIP_BASE64))) as pacote:
    for nome in pacote.namelist():
        alvo = (RAIZ_EXP / nome).resolve()
        assert alvo.is_relative_to(RAIZ_EXP.resolve())
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_bytes(pacote.read(nome))
for nome, esperado in MANIFESTO_FONTES.items():
    assert sha256((RAIZ_EXP / nome).read_bytes()).hexdigest() == esperado
REL = RAIZ_EXP / "relatorios"
REL.mkdir(exist_ok=True)
MODELOS_ORIGINAIS = {nome: sha256((RAIZ_EXP / nome).read_bytes()).hexdigest() for nome in ("modelo/arvore.json", "modelo/arvore.joblib")}
AMBIENTE = dict(os.environ)
AMBIENTE["OPENAI_API_KEY"] = ""
AMBIENTE["MPLBACKEND"] = "Agg"
COMANDOS_EXECUTADOS = []

def executar_script(nome):
    resposta = subprocess.run([sys.executable, str(RAIZ_EXP / "scripts" / nome)], cwd=RAIZ_EXP, env=AMBIENTE, text=True, capture_output=True, check=True)
    COMANDOS_EXECUTADOS.append(nome)
    print(f"Concluído: python scripts/{nome}")
    return resposta

def carregar_json(nome):
    return json.loads((REL / nome).read_text(encoding="utf-8"))

def figura(nome, largura=900):
    display(Image(filename=str(REL / "figuras" / nome), width=largura))

print("Fontes e dados conferidos; execução isolada, sem relatórios pré-calculados.")""")
    md("""## 2. Problema, dados fictícios e política de rotulagem

X contém risco à segurança, interrupção de serviço essencial, pessoas afetadas, dias aguardando e recorrência. O alvo y é `prioridade`: 0 = normal, 1 = prioritário. IDs, descrições e famílias não entram nesses modelos numéricos.

A política atribui prioridade quando há risco, interrupção essencial, pelo menos 40 pessoas e 7 dias, ou recorrência com pelo menos 10 pessoas e 14 dias. Os limiares são pedagógicos. Variações da mesma família permanecem juntas. A primeira partição agrupada com semente 42 preserva os conjuntos originais; o teste reservado não participa de escolha de hiperparâmetros ou da decisão de integrar o modelo textual.""")
    code("""sys.path.insert(0, str(RAIZ_EXP))
from scripts.ml_comum import FEATURES, carregar_dados, divisao_original, politica, hash_dados_numericos
base = carregar_dados(RAIZ_EXP)
idx_treino, idx_teste = divisao_original(base)
assert not set(base.iloc[idx_treino].familia_cenario) & set(base.iloc[idx_teste].familia_cenario)
assert np.array_equal(base.prioridade.to_numpy(), politica(base))
display(pd.DataFrame([{"conjunto": nome, "registros": len(parte), "famílias": parte.familia_cenario.nunique(), "normais": int((parte.prioridade == 0).sum()), "prioritários": int((parte.prioridade == 1).sum())} for nome, parte in [("Base", base), ("Desenvolvimento", base.iloc[idx_treino]), ("Teste reservado", base.iloc[idx_teste])]]))
print("SHA256 dos dados numéricos:", hash_dados_numericos(base))
display(base.head())""")
    md("""## 3. Baselines e validação cruzada agrupada com incerteza

Comparamos Dummy de maioria, política de regras, árvore com profundidade 6, regressão logística com padronização e Random Forest. A validação principal usa somente o desenvolvimento, com cinco folds e dez sementes distintas. O pré-processamento é ajustado no treino de cada fold. Para continuidade, o teste reservado é avaliado separadamente; a árvore original do aplicativo é carregada sem regravação.

A média e o desvio-padrão amostral resumem métricas OOF agregadas por repetição. O bootstrap reamostra famílias inteiras, mantendo variações e repetições juntas. Seus intervalos são condicionais às famílias fictícias disponíveis: repetir folds não cria observações independentes. O histórico de escolha da profundidade também limita a interpretação desta avaliação de configurações fixas.""")
    code("""executar_script("avaliar_modelos.py")
comparacao = carregar_json("comparacao_modelos.json")
linhas = []
for modelo, registro in comparacao["modelos"].items():
    for metrica, resumo in registro["validacao_cruzada"].items():
        linhas.append({"modelo": modelo, "métrica": metrica, "média OOF": resumo["media"], "desvio-padrão": resumo["desvio_padrao"], "IC95% por famílias": resumo["ic95_bootstrap_familias"]})
display(pd.DataFrame(linhas))
display(pd.DataFrame({nome: registro["teste_reservado"] for nome, registro in comparacao["modelos"].items()}).T)
display(comparacao["protocolo"])
print("Famílias de desenvolvimento:", base.iloc[idx_treino].familia_cenario.nunique())""")
    md("""## 4. Árvore publicada e interpretabilidade

Interpretamos o estimador já usado no aplicativo, sem retreiná-lo. Importância por redução de impureza descreve esse ajuste e não demonstra causalidade. Nos domínios inteiros, um corte `<= 39,5` separa os mesmos valores que a condição `>= 40`. A tabela permite distinguir cortes numericamente diferentes de decisões realmente diferentes. A ordem dos testes pode reorganizar a expressão lógica sem mudar a regra.""")
    code("""executar_script("interpretar_arvore.py")
interpretacao = carregar_json("interpretabilidade.json")
print((REL / "arvore_interpretada.txt").read_text(encoding="utf-8"))
display(pd.DataFrame(interpretacao["limiares"]))
display(pd.DataFrame(interpretacao["importancias"]))
print(interpretacao["interpretacao"])
display(interpretacao["consistencia_celulas"])
figura("arvore_publicada.png", 1100)
figura("importancias_arvore.png")""")
    md("""## 5. Fronteiras da política e análise de erros fora da amostra

A grade combina pessoas 8–12 e 38–42, dias 5–9 e 12–16 e os três indicadores binários. Ela foi derivada da própria política: mede consistência e cobertura de fronteiras, não validação externa. As taxas de falsos negativos usam como denominador os positivos de cada região; regiões sem positivos não permitem essa taxa.

Erros OOF são separados dos erros da grade. Cada previsão OOF foi produzida com a família correspondente fora do treino. O mesmo caso pode reaparecer em repetições; listagens e matrizes somadas não representam novos chamados independentes.""")
    code("""executar_script("analisar_fronteiras.py")
fronteiras = carregar_json("fronteiras.json")
display(pd.DataFrame(fronteiras["modelos"]).T)
display(pd.DataFrame(fronteiras["taxas_por_regiao"]))
print(fronteiras["interpretacao"])
erros = pd.DataFrame(comparacao["erros_oof"])
print("Previsões OOF erradas, incluindo repetições:", len(erros))
if len(erros):
    display(erros.groupby(["modelo", "tipo_erro"]).size().rename("ocorrências").reset_index())
    display(erros.head(30))
    print("A lista completa está em relatorios/erros_oof_modelos.csv desta execução.")
else:
    print("Nenhum erro OOF observado neste protocolo; isso não garante ausência de erro real.")
for nome in ("fronteiras_arvore.png", "fronteiras_logistica.png", "fronteiras_randomforest.png"):
    figura(nome)""")
    md("""## 6. Experimento de ruído nos rótulos

Invertemos rótulos somente no treino original e avaliamos no teste reservado limpo. Comparamos ruído uniforme e concentrado nas fronteiras, com o mesmo número de inversões por taxa e semente. A unidade é o registro; os dados originais permanecem intactos. As taxas nominais de 0%, 5%, 10%, 15% e 20% são acompanhadas das taxas efetivas após arredondamento.

Além dos modelos anteriores, testamos árvore limitada a profundidade 3 e árvore cuja profundidade é escolhida por GridSearchCV agrupado exclusivamente no treino ruidoso. O baseline de regras ignora rótulos de treino por definição. O desacordo de fronteira é uma simulação escolhida pelo autor, não uma estimativa de como pessoas reais rotulariam chamados.""")
    code("""executar_script("experimento_ruido.py")
ruido = carregar_json("experimento_ruido.json")
resumo_ruido = []
for linha in ruido["resumo"]:
    resumo_ruido.append({"modelo": linha["modelo"], "modo": linha["modo"], "taxa nominal": linha["taxa_nominal"], "taxa efetiva": linha["taxa_efetiva"], **{f"{m}_{k}": v for m, registro in linha["metricas"]["teste_limpo"].items() for k, v in registro.items()}})
display(pd.DataFrame(resumo_ruido))
display(ruido["protocolo"])
profundidades = [{"modo": r["modo"], "taxa": r["taxa_nominal"], "frequências": r.get("frequencia_max_depth_escolhido", {})} for r in ruido["resumo"] if "Grid" in r["modelo"] or r.get("frequencia_max_depth_escolhido")]
display(pd.DataFrame(profundidades))
figura("ruido_sensibilidade.png", 1000)
figura("ruido_f2.png", 1000)""")
    md("""### Como interpretar robustez e overfitting

Compare treino ruidoso, treino limpo e teste limpo, além das faixas de desvio nos gráficos. Maior ajuste aos rótulos perturbados com pior desempenho limpo é evidência de sensibilidade ao ruído neste experimento. Não se deve afirmar que limitar profundidade ou trocar algoritmo sempre melhora: essa conclusão depende dos resultados medidos, do modo de perturbação e das famílias do teste. A configuração vencedora sob ruído não será promovida ao aplicativo com base neste teste reutilizado.""")
    md("""## 7. Curva de aprendizado por número de famílias

Subconjuntos aninhados de famílias do treino são usados para ajustar árvore e regressão logística, mantendo famílias externas para validação. O teste reservado não entra nesta curva. A dispersão entre partições sobrepostas é descritiva, e a curva pode não ser monotônica.

Um patamar em exemplos rotulados por regras não comprova que a quantidade atual de dados baste para uma instituição. A aquisição de famílias independentes e rótulos revisados por especialistas continua necessária.""")
    code("""executar_script("curva_aprendizado.py")
curva = carregar_json("curva_aprendizado.json")
display(pd.json_normalize(curva["resumos"], sep=" · "))
display(curva["protocolo"])
figura("curva_aprendizado.png")""")
    md("""## 8. Classificador de texto para equipe

Cada família recebe uma anotação didática manual de equipe e uma justificativa. A entrada é somente a descrição; o sufixo sintético com contagens é removido antes da vetorização. O pipeline combina TF-IDF de palavras/bigramas e de n-gramas de caracteres com regressão logística. TF-IDF e classificador são ajustados dentro de cada fold agrupado.

Comparamos a regra local de palavras-chave nas mesmas partições de desenvolvimento. A integração depende de superar estritamente a regra tanto em acurácia média quanto em F1 macro médio. O gate é decidido antes de consultar o reservado. Se não superar, o artefato textual continua experimental e a regra permanece no Flask. Texto e equipe jamais mudam a classificação de prioridade pela árvore.""")
    code("""executar_script("treinar_texto.py")
texto = carregar_json("classificador_texto.json")
linhas_texto = []
for nome, registro in texto["modelos"].items():
    linhas_texto.append({"modelo": nome, **{f"{m}_{k}": v for m in ("acuracia", "f1_macro") for k, v in registro[m].items()}})
    print(nome, "matriz OOF somada; ordem das classes:", texto["ordem_classes"])
    display(pd.DataFrame(registro["matriz_confusao_oof_somada"], index=texto["ordem_classes"], columns=texto["ordem_classes"]))
    print("Erros OOF, incluindo repetições:", len(registro["erros_oof"]))
    display(pd.DataFrame(registro["erros_oof"]).head(12))
display(pd.DataFrame(linhas_texto))
display(texto["gate"])
display(texto["teste_reservado"])
display(texto.get("suporte_teste_reservado", {}))
print("A partição reservada foi estratificada por prioridade, não por equipe. Consulte o suporte por classe; o F1 macro usa a ordem fixa de quatro classes, inclusive quando uma classe está ausente.")
display(pd.read_csv(RAIZ_EXP / "dados/rotulagem_equipes.csv"))""")
    md("""## 9. Ameaças à validade e continuidade

- **Circularidade dos rótulos:** regras geram o alvo; uma árvore bem ajustada reaprende essa função. A regra explícita é a solução simples quando a política é conhecida e estável.
- **Dados fictícios e amostra pequena:** as famílias foram escolhidas pelo autor, sem parceiro institucional. Métricas não comprovam segurança ou eficácia real.
- **Dependência:** as quatro variações de cada família compartilham contexto; folds e repetições compartilham dados. Bootstrap por família reduz a unidade indevida de reamostragem, sem resolver todas as incertezas.
- **Histórico de seleção:** a profundidade da árvore já havia sido escolhida no desenvolvimento original. A avaliação de configurações fixas não representa uma avaliação aninhada de toda a seleção anterior.
- **Grade sintética:** deriva dos mesmos limiares e serve para consistência, não para validade externa.
- **Ruído simulado:** os mecanismos de inversão foram propostos para estudo, sem medição de desacordo humano real. Reutilizar o reservado em curvas não autoriza escolher o vencedor e declarar uma nova estimativa imparcial.
- **Texto:** os rótulos de equipe são didáticos, há poucas famílias por classe e enunciados repetidos; a avaliação por família é indispensável. Sem superar a regra, o modelo treinado não deve substituir o fallback.

Em uma parceria real, coletar contextos independentes, anonimizar descrições, manter desconhecidos ausentes, obter rótulos justificados de avaliadores técnicos e reservar famílias e períodos futuros. A triagem e a ordem de atendimento permanecem humanas.""")
    md("""## 10. Integridade e artefatos regenerados

Todos os resultados exibidos acima foram calculados nesta execução. O bloco final confere que os experimentos não alteraram a árvore incorporada. O diretório `RAIZ_EXP` mantém as fontes, tabelas e figuras durante a sessão; não há banco SQLite, uploads ou credenciais incorporados.""")
    code("""for nome, esperado in MODELOS_ORIGINAIS.items():
    assert sha256((RAIZ_EXP / nome).read_bytes()).hexdigest() == esperado
assert set(COMANDOS_EXECUTADOS) == {"avaliar_modelos.py", "interpretar_arvore.py", "analisar_fronteiras.py", "experimento_ruido.py", "curva_aprendizado.py", "treinar_texto.py"}
assert not (RAIZ_EXP / ".env").exists()
assert not (RAIZ_EXP / "instance").exists()
print("Árvore original preservada; todos os experimentos regenerados; sem API externa.")
print("Relatórios e figuras disponíveis na variável REL desta sessão.")""")
    notebook = nbformat.v4.new_notebook(cells=cells)
    notebook.metadata = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"},
                         "projeto": {"autor": "Guilherme Costa", "origem": "Dados inteiramente fictícios", "isolamento": "TemporaryDirectory", "fontes_sha256": manifesto}}
    # IDs estáveis para reduzir diffs que não representam mudanças no conteúdo.
    for i, cell in enumerate(notebook.cells):
        cell.id = f"ml-{i:02d}"
    return notebook, manifesto


def executar_notebook(raiz=ROOT):
    from nbclient import NotebookClient
    raiz = Path(raiz)
    protegidos = {nome: sha256((raiz / nome).read_bytes()).hexdigest() for nome in PROTEGIDOS}
    notebook, manifesto = montar(raiz)
    NotebookClient(notebook, timeout=1800, kernel_name="python3", resources={"metadata": {"path": str(raiz)}}, record_timing=False).execute()
    for nome, esperado in protegidos.items():
        if sha256((raiz / nome).read_bytes()).hexdigest() != esperado:
            raise AssertionError(f"Artefato protegido foi modificado: {nome}")
    for cell in notebook.cells:
        cell.metadata.pop("execution", None)
    destino = raiz / "Projeto_Chamados_Manutencao.ipynb"
    nbformat.write(notebook, destino)
    codigos = [c for c in notebook.cells if c.cell_type == "code"]
    erros = [o for c in codigos for o in c.outputs if o.output_type == "error"]
    relatorio = {"ambiente": "Kernel local limpo executado com nbclient; compatível com Google Colab, sem afirmar execução no serviço Google.",
        "notebook": destino.name, "celulas_codigo": len(codigos), "celulas_executadas": len([c for c in codigos if c.execution_count is not None]),
        "saidas_erro": len(erros), "resultado": "aprovado" if not erros else "reprovado",
        "isolamento": "Fontes, dados e modelos extraídos em TemporaryDirectory; relatórios integralmente regenerados.",
        "scripts_executados": ["avaliar_modelos.py", "interpretar_arvore.py", "analisar_fronteiras.py", "experimento_ruido.py", "curva_aprendizado.py", "treinar_texto.py"],
        "fontes_sha256": manifesto, "artefatos_app_preservados": protegidos,
        "chamadas_openai": 0, "sementes_fixas": True, "relatorios_precalculados_embutidos": False}
    diretorio = raiz / "relatorios"; diretorio.mkdir(exist_ok=True)
    (diretorio / "execucao_notebook.json").write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return relatorio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executar", action="store_true", help="Executa em kernel limpo e salva todas as saídas.")
    args = parser.parse_args()
    if args.executar:
        print(json.dumps(executar_notebook(), ensure_ascii=False, indent=2))
    else:
        notebook, _ = montar()
        nbformat.write(notebook, ROOT / "Projeto_Chamados_Manutencao.ipynb")
        print("Notebook autocontido montado; use --executar para conservar saídas verificadas.")
