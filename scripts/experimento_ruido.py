"""Corrupção controlada de rótulos fictícios: somente no treino, teste limpo.

Execute: python scripts/experimento_ruido.py
Nenhum artefato da árvore utilizada pelo aplicativo é alterado.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import fbeta_score, make_scorer
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ml_comum import (ROOT, FEATURES, carregar_dados, criar_modelos, divisao_original,
                      hash_dados_numericos, metricas, politica, salvar_json, versoes)

TAXAS = (0., .05, .10, .15, .20)
MODOS = ("uniforme", "fronteira")
SEEDS = tuple(range(42, 62))
PROFUNDIDADES = [1, 2, 3, 4, 5, 6, None]


def pesos_fronteira(X):
    """Distância à classe oposta com flags fixas; não consulta rótulos do teste.

    Enumeramos pontos críticos das duas regiões retangulares da política. As
    escalas de cinco pessoas e três dias e o decaimento quadrático são escolhas
    didáticas, não estimativas empíricas de desacordo humano.
    """
    valores = X[FEATURES].to_numpy() if isinstance(X, pd.DataFrame) else np.asarray(X)
    pesos = np.zeros(len(valores), dtype=float)
    for i, linha in enumerate(valores):
        risco, essencial, pessoas, dias, recorrente = map(int, linha)
        if risco or essencial:
            continue
        ps = sorted({pessoas, 9, 10, 39, 40})
        ds = sorted({dias, 6, 7, 13, 14})
        grade = np.array([[0, 0, p, d, recorrente] for p in ps for d in ds])
        diferentes = grade[politica(grade) != politica(np.array([linha]))[0]]
        distancia = np.min(np.abs(diferentes[:, 2] - pessoas) / 5 +
                           np.abs(diferentes[:, 3] - dias) / 3)
        pesos[i] = 1 / (.25 + distancia) ** 2
    return pesos


def gerar_ruido(X, y, taxa, seed, modo):
    """Inverte exatamente round(taxa*n) posições do vetor recebido, sem mutá-lo."""
    if modo not in MODOS or not 0 <= taxa <= .5:
        raise ValueError("Modo ou taxa de ruído inválido.")
    limpo = np.asarray(y, dtype=int)
    if not set(limpo) <= {0, 1} or len(limpo) != len(X):
        raise ValueError("Forneça rótulos binários compatíveis com o treino.")
    n = int(round(float(taxa) * len(limpo)))
    gerador = np.random.default_rng(seed)
    p = None
    if modo == "fronteira":
        pesos = pesos_fronteira(X)
        if n > np.count_nonzero(pesos):
            raise ValueError("Não há registros elegíveis suficientes na fronteira.")
        if pesos.sum():
            p = pesos / pesos.sum()
    indices = np.sort(gerador.choice(len(limpo), size=n, replace=False, p=p))
    ruidoso = limpo.copy()
    ruidoso[indices] = 1 - ruidoso[indices]
    return ruidoso, indices


def treinar_avaliar(X_treino, y_ruidoso, y_limpo, grupos, X_teste, y_teste):
    modelos = criar_modelos(seed=42)
    modelos["ArvoreLimitada"] = DecisionTreeClassifier(max_depth=3, random_state=42)
    modelos["ArvoreGridSearch"] = GridSearchCV(
        DecisionTreeClassifier(random_state=42), {"max_depth": PROFUNDIDADES},
        cv=StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=42),
        scoring=make_scorer(fbeta_score, beta=2, zero_division=0),
        n_jobs=1, error_score="raise",
    )
    resultados = []
    for nome, modelo in modelos.items():
        if nome == "ArvoreGridSearch":
            modelo.fit(X_treino, y_ruidoso, groups=grupos)
            arvore = modelo.best_estimator_
            profundidade_escolhida = modelo.best_params_["max_depth"]
            f2_cv = float(modelo.best_score_)
        else:
            modelo.fit(X_treino, y_ruidoso)
            arvore = modelo
            profundidade_escolhida, f2_cv = None, None
        predito_treino = modelo.predict(X_treino)
        resultados.append({
            "modelo": nome,
            "metricas_teste_limpo": metricas(y_teste, modelo.predict(X_teste)),
            "metricas_treino_ruidoso": metricas(y_ruidoso, predito_treino),
            "metricas_treino_limpo": metricas(y_limpo, predito_treino),
            "max_depth_escolhido": profundidade_escolhida,
            "profundidade_aprendida": arvore.get_depth() if isinstance(arvore, DecisionTreeClassifier) else None,
            "melhor_f2_cv_treino_ruidoso": f2_cv,
        })
    return resultados


def resumir(execucoes):
    linhas = []
    for modo in MODOS:
        taxas = sorted({r["taxa_nominal"] for r in execucoes if r["modo"] == modo})
        for taxa in taxas:
            nomes = list(dict.fromkeys(r["modelo"] for r in execucoes))
            for nome in nomes:
                registros = [r for r in execucoes if r["modo"] == modo and r["taxa_nominal"] == taxa and r["modelo"] == nome]
                medidas = {}
                for conjunto in ("teste_limpo", "treino_ruidoso", "treino_limpo"):
                    medidas[conjunto] = {}
                    for metrica in registros[0]["metricas_"+conjunto]:
                        valores = [r["metricas_"+conjunto][metrica] for r in registros]
                        medidas[conjunto][metrica] = {"media": float(np.mean(valores)),
                            "desvio_padrao": float(np.std(valores, ddof=1)) if len(valores)>1 else 0.}
                profundidades = Counter("sem_limite" if r["max_depth_escolhido"] is None else str(r["max_depth_escolhido"])
                                        for r in registros) if nome == "ArvoreGridSearch" else {}
                linhas.append({"modo": modo, "taxa_nominal": taxa,
                    "taxa_efetiva": registros[0]["taxa_efetiva"], "modelo": nome,
                    "repeticoes": len(registros), "metricas": medidas,
                    "frequencia_max_depth_escolhido": dict(profundidades)})
    return linhas


def plotar(resumo, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = list(dict.fromkeys(r["modelo"] for r in resumo))
    for metrica, titulo in [("sensibilidade", "Sensibilidade da classe prioritária"), ("f2", "F2 da classe prioritária")]:
        fig, eixos = plt.subplots(1, 2, figsize=(13, 5), sharey=True, constrained_layout=True)
        for eixo, modo in zip(eixos, MODOS):
            for indice, nome in enumerate(nomes):
                linhas = [r for r in resumo if r["modo"] == modo and r["modelo"] == nome]
                x = np.array([r["taxa_efetiva"]*100 for r in linhas])
                y = np.array([r["metricas"]["teste_limpo"][metrica]["media"] for r in linhas])
                sd = np.array([r["metricas"]["teste_limpo"][metrica]["desvio_padrao"] for r in linhas])
                estilo = "--" if nome == "Regras" else "-"
                cor = "black" if nome == "Regras" else f"C{indice}"
                eixo.plot(x, y, estilo, marker="o", markersize=4, label=nome, color=cor)
                eixo.fill_between(x, np.maximum(0,y-sd), np.minimum(1,y+sd), alpha=.09, color=cor)
            eixo.set(title="Ruído uniforme" if modo == "uniforme" else "Ruído concentrado nas fronteiras",
                     xlabel="Rótulos de treino invertidos (%)", ylim=(-.03,1.04))
            eixo.grid(alpha=.2)
        eixos[0].set_ylabel(titulo)
        eixos[-1].legend(fontsize=8, loc="lower left", ncol=2)
        fig.suptitle("Teste limpo reservado; média e faixa de um desvio-padrão entre sementes")
        fig.savefig(pasta/f"ruido_{metrica}.png", dpi=170)
        plt.close(fig)


def executar(raiz=ROOT, seeds=SEEDS, taxas=TAXAS):
    raiz = Path(raiz)
    seeds, taxas = tuple(seeds), tuple(taxas)
    if not seeds or len(set(seeds)) != len(seeds) or not taxas:
        raise ValueError("Informe sementes distintas e taxas não vazias.")
    df = carregar_dados(raiz)
    antes = df.copy(deep=True)
    treino, teste = divisao_original(df)
    X_treino, X_teste = df.iloc[treino][FEATURES], df.iloc[teste][FEATURES]
    y_treino, y_teste = df.iloc[treino].prioridade.to_numpy(), df.iloc[teste].prioridade.to_numpy()
    grupos = df.iloc[treino].familia_cenario.to_numpy()
    execucoes, cache = [], {}
    for modo in MODOS:
        for taxa in taxas:
            for seed in seeds:
                y_ruidoso, indices = gerar_ruido(X_treino, y_treino, taxa, seed, modo)
                chave = tuple(indices.tolist())
                if chave not in cache:
                    cache[chave] = treinar_avaliar(X_treino, y_ruidoso, y_treino, grupos, X_teste, y_teste)
                ids = df.iloc[treino].iloc[indices].id.tolist()
                for resultado in cache[chave]:
                    execucoes.append({"modo": modo, "taxa_nominal": float(taxa), "seed_ruido": int(seed),
                        "quantidade_invertida": len(indices), "taxa_efetiva": len(indices)/len(treino),
                        "ids_invertidos": ids, **resultado})
    pd.testing.assert_frame_equal(df, antes)
    assert np.array_equal(y_teste, df.iloc[teste].prioridade.to_numpy())
    resumo = resumir(execucoes)
    relatorio = {
        "experimento": "Ruído artificial nos rótulos de treino; teste reservado limpo",
        "dados": "Chamados inteiramente fictícios; política conhecida e determinística",
        "hash_dados_numericos": hash_dados_numericos(df), "versoes": versoes(),
        "protocolo": {
            "unidade_corrupcao": "registro, não família", "seeds_ruido": list(seeds),
            "seed_modelos": 42, "separacao": "primeira partição StratifiedGroupKFold 5, seed 42",
            "taxas_nominais": list(taxas), "arredondamento": "round(taxa * n_treino); mesma quantidade nos dois modos",
            "treino_ids": df.iloc[treino].id.tolist(), "teste_ids": df.iloc[teste].id.tolist(),
            "familias_treino": sorted(set(grupos)), "familias_teste": sorted(set(df.iloc[teste].familia_cenario)),
            "fronteira": "Somente risco=essencial=0; distância L1 à classe oposta na política, com flags fixas. Candidatos pessoas={valor,9,10,39,40}, dias={valor,6,7,13,14}. Distância normalizada por 5 pessoas e 3 dias; peso=1/(0.25+distância)^2. Amostragem sem reposição.",
            "grade_profundidade": PROFUNDIDADES, "cv_selecao": "4 folds por família, seed 42, F2, exclusivamente no treino corrompido; empate favorece menor profundidade",
            "cache": "Repetições com exatamente os mesmos rótulos reutilizam ajustes determinísticos, sem alterar as observações registradas.",
            "estatistica": "Média e desvio-padrão amostral entre sementes; não é intervalo de confiança nem variabilidade entre instituições.",
        },
        "execucoes": execucoes, "resumo": resumo,
        "limites": [
            "O desacordo concentrado é uma hipótese sintética de anotação, não foi medido em pessoas.",
            "Regras não aprendem rótulos: permanecem perfeitas quando a política conhecida é o alvo limpo.",
            "O mesmo teste pequeno é consultado repetidamente em análise exploratória; não serve para selecionar uma nova versão do aplicativo.",
            "Nenhum registro de teste foi corrompido ou usado no GridSearchCV.",
            "A árvore principal do aplicativo não é regravada nem selecionada pelos resultados deste estudo.",
        ],
    }
    salvar_json(raiz/"relatorios/experimento_ruido.json", relatorio)
    tabela = []
    for r in resumo:
        linha = {k:r[k] for k in ("modo","taxa_nominal","taxa_efetiva","modelo","repeticoes")}
        for m,v in r["metricas"]["teste_limpo"].items():
            linha[m+"_media"], linha[m+"_desvio_padrao"] = v["media"], v["desvio_padrao"]
        tabela.append(linha)
    pd.DataFrame(tabela).to_csv(raiz/"relatorios/experimento_ruido.csv",index=False)
    plotar(resumo, raiz/"relatorios/figuras")
    print("Experimento de ruído concluído:",len(execucoes),"avaliações,",len(seeds),"sementes.")
    return relatorio


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeticoes",type=int,default=20)
    args=parser.parse_args()
    if args.repeticoes < 20:
        parser.error("Use pelo menos 20 repetições no relatório principal.")
    executar(seeds=range(42,42+args.repeticoes))
