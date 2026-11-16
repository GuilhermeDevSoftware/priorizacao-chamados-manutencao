"""Compara configurações fixas usando OOF por família e bootstrap de famílias.

Execute: python scripts/avaliar_modelos.py
Nenhum artefato usado pelo aplicativo é regravado. Todos os dados são fictícios.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold

try:
    from .ml_comum import (ROOT, FEATURES, METRICAS, carregar_dados, criar_modelos, divisao_original,
                           hash_dados_numericos, metricas, salvar_json, versoes)
except ImportError:
    from ml_comum import (ROOT, FEATURES, METRICAS, carregar_dados, criar_modelos, divisao_original,
                         hash_dados_numericos, metricas, salvar_json, versoes)


def _dividir(a, b):
    return np.divide(a, b, out=np.zeros_like(a, dtype=float), where=b != 0)


def metricas_contagens(c):
    """tn, fp, fn, tp; aceita matrizes para bootstrap vetorizado."""
    tn, fp, fn, tp = np.moveaxis(np.asarray(c), -1, 0)
    return {
        "sensibilidade": _dividir(tp, tp + fn),
        "precisao": _dividir(tp, tp + fp),
        "f1": _dividir(2 * tp, 2 * tp + fp + fn),
        "f2": _dividir(5 * tp, 5 * tp + 4 * fn + fp),
        "acuracia": _dividir(tn + tp, tn + fp + fn + tp),
    }


def bootstrap_familias(y, predicoes, grupos, amostras=1000, seed=4242):
    """IC percentil: reamostra famílias inteiras e mantém repetições dependentes juntas.

    predicoes tem dimensões (repetição, registro). Cada estatística bootstrap é a
    média das métricas OOF agregadas de todas as repetições. Não se reamostram
    folds como se fossem independentes, nem se infla o tamanho amostral por 10.
    """
    if amostras < 1:
        raise ValueError("O bootstrap precisa de pelo menos uma amostra.")
    grupos = np.asarray(grupos)
    y = np.asarray(y)
    predicoes = np.asarray(predicoes)
    familias, codigos = np.unique(grupos, return_inverse=True)
    n = len(familias)
    rng = np.random.default_rng(seed)
    escolhidas = rng.integers(n, size=(amostras, n))
    pesos = np.eye(n, dtype=int)[escolhidas].sum(axis=1)
    contagens = np.empty((len(predicoes), n, 4), dtype=int)
    for rep, p in enumerate(predicoes):
        estado = 2 * y + p  # 0=tn, 1=fp, 2=fn, 3=tp
        for k in range(4):
            contagens[rep, :, k] = np.bincount(codigos, weights=(estado == k), minlength=n)
    totais = np.einsum("bf,rfk->brk", pesos, contagens)
    return {nome: np.quantile(valores.mean(axis=1), [0.025, 0.975]).tolist()
            for nome, valores in metricas_contagens(totais).items()}


def executar(raiz=ROOT, repeticoes=10, bootstrap=1000):
    if repeticoes < 1:
        raise ValueError("Informe pelo menos uma repetição.")
    raiz = Path(raiz)
    destino = raiz / "relatorios"
    destino.mkdir(parents=True, exist_ok=True)
    df = carregar_dados(raiz)
    itreino, iteste = divisao_original(df)
    dev = df.iloc[itreino].reset_index(drop=True)
    teste = df.iloc[iteste].reset_index(drop=True)
    X, y, grupos = dev[FEATURES], dev.prioridade.to_numpy(), dev.familia_cenario.to_numpy()
    nomes = list(criar_modelos())
    previsoes = {nome: np.full((repeticoes, len(dev)), -1, dtype=int) for nome in nomes}
    resultados_repeticoes, resultados_folds, auditoria = [], [], []
    seeds = list(range(42, 42 + repeticoes))
    folds_de_cada_registro = np.full((repeticoes, len(dev)), -1, dtype=int)
    for repeticao, seed in enumerate(seeds):
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for fold, (treino, validacao) in enumerate(cv.split(X, y, grupos)):
            familias_treino, familias_validacao = sorted(set(grupos[treino])), sorted(set(grupos[validacao]))
            assert not set(familias_treino) & set(familias_validacao)
            assert not set(grupos[validacao]) & set(teste.familia_cenario)
            auditoria.append({"repeticao": repeticao, "seed": seed, "fold": fold,
                              "familias_treino": familias_treino, "familias_validacao": familias_validacao})
            folds_de_cada_registro[repeticao, validacao] = fold
            for nome, modelo in criar_modelos(seed=42).items():
                modelo.fit(X.iloc[treino], y[treino])
                p = modelo.predict(X.iloc[validacao]).astype(int)
                previsoes[nome][repeticao, validacao] = p
                resultados_folds.append({"repeticao": repeticao, "seed": seed, "fold": fold,
                                          "modelo": nome, "registros_validacao": len(validacao),
                                          **metricas(y[validacao], p)})
        for nome in nomes:
            assert np.all(previsoes[nome][repeticao] >= 0)
            resultados_repeticoes.append({"repeticao": repeticao, "seed": seed, "modelo": nome,
                                          **metricas(y, previsoes[nome][repeticao])})
    tabela_repeticoes = pd.DataFrame(resultados_repeticoes)
    erros = []
    oof = []
    for repeticao, seed in enumerate(seeds):
        for pos, registro in dev.iterrows():
            dados = registro[["id", "familia_cenario", "descricao", *FEATURES, "prioridade"]].to_dict()
            linha = {"repeticao": repeticao, "seed": seed, "fold": int(folds_de_cada_registro[repeticao, pos]), **dados}
            for nome in nomes:
                p = int(previsoes[nome][repeticao, pos])
                linha["previsto_" + nome] = p
                if p != int(registro.prioridade):
                    erros.append({"modelo": nome, "repeticao": repeticao, "seed": seed,
                                  "fold": linha["fold"], **dados, "previsto": p,
                                  "tipo_erro": "falso_negativo" if registro.prioridade == 1 else "falso_positivo"})
            oof.append(linha)
    modelos_reservado = criar_modelos(seed=42)
    modelos_reservado["Arvore"] = joblib.load(raiz / "modelo/arvore.joblib")
    resultados, linhas_tabela = {}, []
    for nome, modelo in modelos_reservado.items():
        if nome != "Arvore":
            modelo.fit(dev[FEATURES], dev.prioridade)
        previsto = modelo.predict(teste[FEATURES]).astype(int)
        reservado = metricas(teste.prioridade, previsto)
        intervalos = bootstrap_familias(y, previsoes[nome], grupos, amostras=bootstrap)
        medidas = tabela_repeticoes.loc[tabela_repeticoes.modelo == nome]
        resumo = {}
        for metrica in METRICAS:
            resumo[metrica] = {"media": float(medidas[metrica].mean()),
                              "desvio_padrao": float(medidas[metrica].std(ddof=1)) if repeticoes > 1 else 0.0,
                              "ic95_bootstrap_familias": intervalos[metrica]}
            linhas_tabela.append({"modelo": nome, "metrica": metrica, **resumo[metrica],
                                  "ic95_inferior": intervalos[metrica][0], "ic95_superior": intervalos[metrica][1],
                                  "teste_reservado": reservado[metrica]})
        resultados[nome] = {
            "validacao_cruzada": resumo, "teste_reservado": reservado,
            "matriz_confusao_teste": confusion_matrix(teste.prioridade, previsto, labels=[0, 1]).tolist(),
            "erros_oof": int(sum(e["modelo"] == nome for e in erros)),
            "registros_unicos_com_erro_oof": len({e["id"] for e in erros if e["modelo"] == nome}),
            "familias_com_erro_oof": len({e["familia_cenario"] for e in erros if e["modelo"] == nome}),
            "falsos_negativos_oof": int(sum(e["modelo"] == nome and e["tipo_erro"] == "falso_negativo" for e in erros)),
            "predicoes_teste_reservado": [{"id": row.id, "familia_cenario": row.familia_cenario,
                                           "real": int(row.prioridade), "previsto": int(pred)}
                                          for (_, row), pred in zip(teste.iterrows(), previsto)],
        }
    relatorio = {
        "origem": "Dados inteiramente fictícios; rótulos derivados da política explícita.",
        "hash_dados_numericos": hash_dados_numericos(df), "versoes": versoes(),
        "protocolo": {
            "desenvolvimento": {"registros": len(dev), "familias": int(dev.familia_cenario.nunique()), "ids": dev.id.tolist()},
            "teste_reservado": {"registros": len(teste), "familias": int(teste.familia_cenario.nunique()), "ids": teste.id.tolist()},
            "divisao_original": "Primeira partição SGKF5 shuffle=True seed42; teste já consultado na versão original, mantido para continuidade.",
            "validacao": "SGKF5 repetido somente no desenvolvimento, com famílias disjuntas em cada partição.",
            "repeticoes": repeticoes, "seeds_particoes": seeds, "seed_modelos": 42,
            "estatistica_principal": "Média e desvio-padrão amostral das métricas OOF agregadas por repetição; as repetições são dependentes.",
            "bootstrap": {"amostras": bootstrap, "seed": 4242, "nivel": 0.95, "unidade": "família inteira",
                          "metodo": "Percentil; reamostra famílias do desenvolvimento com reposição, mantendo todas as variações e repetições juntas. Estatística: média das métricas OOF por repetição."},
            "hiperparametros": {"Dummy": "most_frequent", "Regras": "política determinística sem aprendizado",
                                "Arvore": {"max_depth": 6, "random_state": 42},
                                "Logistica": {"padronizacao": "StandardScaler ajustado somente no treino do fold", "max_iter": 2000, "random_state": 42},
                                "RandomForest": {"n_estimators": 100, "max_depth": None, "random_state": 42, "n_jobs": 1}},
            "arvore_no_teste": "Estimador original carregado de modelo/arvore.joblib; não regravado.",
        },
        "definicoes_metricas": {"sensibilidade": "VP/(VP+FN), classe prioritária 1",
                               "precisao": "VP/(VP+FP), classe prioritária 1",
                               "f1": "2VP/(2VP+FP+FN), classe prioritária 1",
                               "f2": "5VP/(5VP+4FN+FP), classe prioritária 1",
                               "acuracia": "(VP+VN)/total, métrica global das duas classes",
                               "denominador_zero": "zero_division=0, explicitamente igual ao scikit-learn"},
        "unidade_erros_oof": "Observação de um chamado em uma repetição; IDs podem repetir. Contagens únicas são relatadas por modelo.",
        "modelos": resultados, "por_repeticao": resultados_repeticoes,
        "por_fold": resultados_folds, "particoes_familias": auditoria,
        "erros_oof": erros,
        "limites": [
            "Bootstrap e desvio-padrão condicionados a somente 24 famílias fictícias de desenvolvimento; não medem desempenho real.",
            "Repetir partições não cria novos dados independentes e o intervalo não incorpora todas as incertezas da geração sintética.",
            "A profundidade 6 já havia sido escolhida anteriormente; a CV avalia configurações fixas, não reavalia todo o processo de seleção.",
            "O baseline de regras conhece a função que gerou os rótulos: serve de referência de consistência, não de validação externa.",
            "Com política conhecida e estável, regras explícitas resolvem esta tarefa sem necessidade de ML; os modelos aprendidos são experimentos acadêmicos.",
        ],
    }
    salvar_json(destino / "comparacao_modelos.json", relatorio)
    tabela = pd.DataFrame(linhas_tabela).drop(columns="ic95_bootstrap_familias")
    tabela.to_csv(destino / "comparacao_modelos.csv", index=False, lineterminator="\n")
    pd.DataFrame(oof).to_csv(destino / "predicoes_oof_modelos.csv", index=False, lineterminator="\n")
    pd.DataFrame(erros, columns=["modelo", "repeticao", "seed", "fold", "id", "familia_cenario", "descricao", *FEATURES, "prioridade", "previsto", "tipo_erro"]).to_csv(destino / "erros_oof_modelos.csv", index=False, lineterminator="\n")
    linhas = ["# Comparação dos modelos", "", "CV agrupada repetida somente nos dados de desenvolvimento. Valores: média ± desvio-padrão entre repetições; IC95% por bootstrap de famílias.", "", "| Modelo | Sensibilidade | Precisão | F1 | F2 | Acurácia |", "| --- | --- | --- | --- | --- | --- |"]
    for nome, registro in resultados.items():
        valores = []
        for metrica in METRICAS:
            v = registro["validacao_cruzada"][metrica]; lo, hi = v["ic95_bootstrap_familias"]
            valores.append(f"{v['media']:.4f} ± {v['desvio_padrao']:.4f} [{lo:.4f}; {hi:.4f}]")
        linhas.append("| " + " | ".join([nome, *valores]) + " |")
    linhas.extend(["", "O teste reservado é relatado separadamente no JSON e no CSV. A árvore do aplicativo foi preservada.", "", *relatorio["limites"]])
    (destino / "comparacao_modelos.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return relatorio


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeticoes", type=int, default=10)
    parser.add_argument("--bootstrap", type=int, default=1000)
    args = parser.parse_args()
    resultado = executar(repeticoes=args.repeticoes, bootstrap=args.bootstrap)
    print(json.dumps({nome: dados["validacao_cruzada"] for nome, dados in resultado["modelos"].items()}, ensure_ascii=False, indent=2))
