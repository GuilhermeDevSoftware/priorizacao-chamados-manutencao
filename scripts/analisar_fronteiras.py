"""Grade sintética próxima dos limiares: verificação de consistência, não validação externa."""
from __future__ import annotations

from itertools import product
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from .ml_comum import ROOT, FEATURES, carregar_dados, divisao_original, politica, metricas, criar_modelos, salvar_json, versoes
except ImportError:
    from ml_comum import ROOT, FEATURES, carregar_dados, divisao_original, politica, metricas, criar_modelos, salvar_json, versoes


def gerar_grade():
    pessoas = [*range(8, 13), *range(38, 43)]
    dias = [*range(5, 10), *range(12, 17)]
    linhas = product((0, 1), (0, 1), pessoas, dias, (0, 1))
    grade = pd.DataFrame(linhas, columns=FEATURES)
    grade["regiao_pessoas"] = np.where(grade.pessoas_afetadas <= 12, "8–12", "38–42")
    grade["regiao_dias"] = np.where(grade.dias_aguardando <= 9, "5–9", "12–16")
    grade["prioridade_politica"] = politica(grade[FEATURES])
    return grade


def resumir_erros(y, previsto):
    y, previsto = np.asarray(y), np.asarray(previsto)
    positivos = int(np.count_nonzero(y == 1))
    fn = int(np.count_nonzero((y == 1) & (previsto == 0)))
    fp = int(np.count_nonzero((y == 0) & (previsto == 1)))
    return {"registros": len(y), "positivos_politica": positivos,
            "divergencias": int(np.count_nonzero(y != previsto)),
            "falsos_negativos": fn, "falsos_positivos": fp,
            "taxa_falsos_negativos": fn / positivos if positivos else None}


def resumir_oof(raiz=ROOT):
    arquivo = Path(raiz) / "relatorios/comparacao_modelos.json"
    fonte = "relatorios/comparacao_modelos.json e relatorios/predicoes_oof_modelos.csv"
    if not arquivo.exists():
        return {"disponivel": False, "fonte": fonte,
                "nota": "Execute avaliar_modelos.py para obter erros fora da amostra; a grade não substitui a validação agrupada."}
    comparacao = json.loads(arquivo.read_text(encoding="utf-8"))
    erros = comparacao["erros_oof"]
    nomes = comparacao["modelos"]
    arvore = [erro for erro in erros if erro["modelo"] == "Arvore"]
    return {"disponivel": True, "fonte": fonte,
            "ocorrencias_erro_por_modelo": {nome: sum(erro["modelo"] == nome for erro in erros) for nome in nomes},
            "casos_errados_arvore": arvore,
            "ids_distintos_errados_arvore": sorted({erro["id"] for erro in arvore}),
            "nota": "Um mesmo ID pode errar em várias repetições. As ocorrências não são amostras independentes; todos os casos e modelos estão no relatório de comparação."}


def mapas_calor(grade, modelo, diretorio):
    fig, eixos = plt.subplots(1, 2, figsize=(13, 5.3), sharey=True)
    for recorrente, ax in enumerate(eixos):
        parte = grade[(grade.risco_seguranca == 0) &
                      (grade.servico_essencial_interrompido == 0) &
                      (grade.recorrente == recorrente)].copy()
        # -1 = falso negativo; +1 = falso positivo; 0 = acordo com a política.
        parte["erro"] = parte["previsto_" + modelo] - parte.prioridade_politica
        matriz = parte.pivot(index="dias_aguardando", columns="pessoas_afetadas", values="erro")
        imagem = ax.imshow(matriz.to_numpy(), vmin=-1, vmax=1, cmap="RdBu", origin="lower", aspect="auto")
        ax.set_xticks(range(len(matriz.columns)), matriz.columns)
        ax.set_yticks(range(len(matriz.index)), matriz.index)
        ax.set_xlabel("Pessoas afetadas (valores explícitos da grade)")
        ax.set_title(f"{modelo} · recorrente = {recorrente}")
        for i in range(len(matriz.index)):
            for j in range(len(matriz.columns)):
                valor = int(matriz.iloc[i, j])
                if valor:
                    ax.text(j, i, "FN" if valor == -1 else "FP", ha="center", va="center", fontsize=8, color="white")
    eixos[0].set_ylabel("Dias aguardando")
    fig.subplots_adjust(left=.07, right=.84, bottom=.14, top=.83, wspace=.15)
    barra = fig.add_axes([.88, .20, .015, .56])
    fig.colorbar(imagem, cax=barra, ticks=[-1, 0, 1],
                 label="-1: falso negativo · 0: acordo · +1: falso positivo")
    fig.suptitle("Grade derivada da política · risco = essencial = 0 · não é validação externa")
    fig.savefig(diretorio / f"fronteiras_{modelo.lower()}.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def executar(raiz=ROOT):
    raiz = Path(raiz)
    relatorios = raiz / "relatorios"
    figuras = relatorios / "figuras"
    figuras.mkdir(parents=True, exist_ok=True)
    # A API comum carrega a base do projeto. Um diretório alternativo recebe apenas saídas.
    df = carregar_dados()
    treino, teste = divisao_original(df)
    grade = gerar_grade()
    resultados, regioes, divergencias = {}, [], []
    modelos = criar_modelos()
    modelos["Arvore"] = joblib.load(ROOT / "modelo/arvore.joblib")
    for nome, estimador in modelos.items():
        if nome != "Arvore":
            estimador.fit(df.iloc[treino][FEATURES], df.iloc[treino].prioridade)
        previsto = np.asarray(estimador.predict(grade[FEATURES]), dtype=int)
        grade["previsto_" + nome] = previsto
        resultados[nome] = {**metricas(grade.prioridade_politica, previsto),
                            **resumir_erros(grade.prioridade_politica, previsto)}
        grupos = ["regiao_pessoas", "regiao_dias", "risco_seguranca", "servico_essencial_interrompido", "recorrente"]
        for chaves, parte in grade.groupby(grupos, sort=True):
            resumo = resumir_erros(parte.prioridade_politica, parte["previsto_" + nome])
            regioes.append({"modelo": nome, **dict(zip(grupos, chaves)), **resumo})
        erros = grade.loc[grade.prioridade_politica != previsto,
                         FEATURES + ["regiao_pessoas", "regiao_dias", "prioridade_politica", "previsto_" + nome]].copy()
        erros = erros.rename(columns={"previsto_" + nome: "previsto"})
        erros["modelo"] = nome
        divergencias.extend(erros.to_dict(orient="records"))
        if nome in ("Arvore", "Logistica", "RandomForest"):
            mapas_calor(grade, nome, figuras)
    grade.to_csv(relatorios / "grade_fronteiras.csv", index=False)
    pd.DataFrame(regioes).to_csv(relatorios / "falsos_negativos_regioes.csv", index=False)
    pd.DataFrame(divergencias, columns=FEATURES + ["regiao_pessoas", "regiao_dias", "prioridade_politica", "previsto", "modelo"]).to_csv(relatorios / "divergencias_fronteiras.csv", index=False)
    resultado = {
        "origem": "Grade inteiramente sintética, derivada dos mesmos limiares da política de rotulagem.",
        "finalidade": "Verificação de consistência e cobertura de fronteiras; não é validação externa nem estimativa de erro em instituições reais.",
        "grade": {"registros": len(grade), "pessoas": [*range(8, 13), *range(38, 43)],
                  "dias": [*range(5, 10), *range(12, 17)], "indicadores": [0, 1],
                  "combinacao": "Produto cartesiano dos dois blocos de pessoas, dos dois blocos de dias e dos três indicadores binários, sem duplicatas."},
        "ajuste": {"registros_treino": len(treino), "familias_treino": int(df.iloc[treino].familia_cenario.nunique()),
                    "teste_reservado_nao_usado_no_ajuste": len(teste), "arvore": "Artefato publicado, sem retreinamento.",
                    "outros_modelos": "Mesmo conjunto original de treino e hiperparâmetros fixos da comparação."},
        "modelos": resultados, "taxas_por_regiao": regioes, "divergencias": divergencias,
        "interpretacao": (
            "A árvore não divergiu da política nesta grade." if resultados["Arvore"]["divergencias"] == 0 else
            "Foram observadas divergências entre a árvore e a política nesta grade; consultar tabela de casos."
        ),
        "erros_oof": resumir_oof(raiz),
        "versoes": versoes(),
    }
    salvar_json(relatorios / "fronteiras.json", resultado)
    print("Grade sintética:", len(grade), "registros. Divergências:", {k: v["divergencias"] for k, v in resultados.items()})
    return resultado


if __name__ == "__main__":
    executar()
