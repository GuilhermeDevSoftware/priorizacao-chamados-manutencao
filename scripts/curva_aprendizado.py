"""Curva de aprendizado agrupada, restrita às famílias de desenvolvimento.

Execute: python scripts/curva_aprendizado.py
Nenhum exemplo do teste reservado participa da seleção, ajuste ou validação.
"""
from __future__ import annotations

from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

try:
    from .ml_comum import (ROOT, FEATURES, METRICAS, carregar_dados, criar_modelos,
                          divisao_original, hash_dados_numericos, metricas,
                          salvar_json, versoes)
except ImportError:
    from ml_comum import (ROOT, FEATURES, METRICAS, carregar_dados, criar_modelos,
                         divisao_original, hash_dados_numericos, metricas,
                         salvar_json, versoes)


def ordenar_familias(treino, seed, menor_tamanho):
    """Uma ordem aleatória aninhada, com duas classes no menor prefixo possível.

    O ajuste de cobertura usa apenas os rótulos do treino externo. Não procura
    uma amostra com melhor desempenho nem consulta a validação ou o reservado.
    """
    familias = np.random.default_rng(seed).permutation(
        sorted(treino.familia_cenario.unique())).tolist()
    tamanho = min(menor_tamanho, len(familias))
    prefixo = treino[treino.familia_cenario.isin(familias[:tamanho])]
    classes = set(prefixo.prioridade)
    if len(classes) < 2:
        faltante = ({0, 1} - classes).pop()
        for indice in range(tamanho, len(familias)):
            if faltante in set(treino.loc[treino.familia_cenario.eq(familias[indice]), "prioridade"]):
                familias[tamanho-1], familias[indice] = familias[indice], familias[tamanho-1]
                break
    return familias


def agregar(resultados):
    tabela = pd.DataFrame(resultados)
    resumos = []
    for (modelo, tamanho), grupo in tabela.groupby(["modelo", "familias_treino"], sort=True):
        item = {"modelo": modelo, "familias_treino": int(tamanho),
                "registros_treino": int(grupo.registros_treino.iloc[0]),
                "avaliacoes": len(grupo), "treino": {}, "validacao": {}}
        for conjunto in ("treino", "validacao"):
            for metrica in METRICAS:
                valores = grupo[f"{conjunto}_{metrica}"].to_numpy()
                item[conjunto][metrica] = {
                    "media": float(valores.mean()),
                    "desvio_padrao": float(valores.std(ddof=1)) if len(valores) > 1 else 0.0,
                }
        resumos.append(item)
    return resumos


def desenhar(resumos, destino):
    fig, eixos = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    for eixo, modelo in zip(eixos, ("Arvore", "Logistica")):
        itens = sorted((r for r in resumos if r["modelo"] == modelo), key=lambda r: r["familias_treino"])
        xs = [r["familias_treino"] for r in itens]
        for conjunto, cor, estilo, rotulo in (("treino", "#466587", "--", "Treino"),
                                             ("validacao", "#16745c", "-", "Validação por família")):
            ys = np.array([r[conjunto]["f2"]["media"] for r in itens])
            desvios = np.array([r[conjunto]["f2"]["desvio_padrao"] for r in itens])
            eixo.plot(xs, ys, marker="o", linestyle=estilo, color=cor, label=rotulo)
            eixo.fill_between(xs, np.clip(ys-desvios, 0, 1), np.clip(ys+desvios, 0, 1), color=cor, alpha=.15)
        eixo.set(title="Árvore (profundidade 6)" if modelo == "Arvore" else "Regressão logística",
                 xlabel="Famílias no treino", ylim=(0, 1.04))
        eixo.set_xticks(xs)
        eixo.grid(alpha=.2)
        eixo.legend(loc="lower right", fontsize=8)
    eixos[0].set_ylabel("F2 da classe prioritária")
    fig.suptitle("Curva de aprendizado - dados inteiramente fictícios")
    fig.text(.5, .015, "Faixas: média ± desvio-padrão entre partições; não são intervalos de confiança.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=(0, .055, 1, .95))
    destino = Path(destino); destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, dpi=180)
    plt.close(fig)


def executar(raiz=ROOT, seeds=range(42, 47), tamanhos=(4, 8, 12, 16, 19)):
    raiz = Path(raiz)
    seeds = [int(s) for s in seeds]
    tamanhos = sorted(set(int(t) for t in tamanhos))
    if not seeds or not tamanhos or min(tamanhos) < 2:
        raise ValueError("Informe sementes e tamanhos de pelo menos duas famílias.")
    dados = carregar_dados(raiz)
    idx_treino, idx_reservado = divisao_original(dados)
    desenvolvimento = dados.iloc[idx_treino].reset_index(drop=True)
    reservado = dados.iloc[idx_reservado]
    familias_reservadas = set(reservado.familia_cenario)
    resultados, particoes = [], []
    for seed in seeds:
        externo = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for fold, (idx_tr, idx_val) in enumerate(externo.split(desenvolvimento[FEATURES], desenvolvimento.prioridade,
                                                             desenvolvimento.familia_cenario)):
            treino = desenvolvimento.iloc[idx_tr]
            validacao = desenvolvimento.iloc[idx_val]
            familias_validacao = set(validacao.familia_cenario)
            assert not familias_reservadas & (set(treino.familia_cenario) | familias_validacao)
            ordem = ordenar_familias(treino, seed * 100 + fold, tamanhos[0])
            usados = sorted(set(min(tamanho, len(ordem)) for tamanho in tamanhos))
            particao = {"seed": seed, "fold": fold,
                        "familias_treino_disponiveis": sorted(treino.familia_cenario.unique()),
                        "familias_validacao": sorted(familias_validacao),
                        "ids_validacao": validacao.id.tolist(), "subconjuntos": []}
            for tamanho in usados:
                familias = ordem[:tamanho]
                amostra = treino[treino.familia_cenario.isin(familias)]
                assert not set(familias) & familias_validacao
                if amostra.prioridade.nunique() != 2:
                    raise ValueError("O subconjunto de treino não contém as duas classes.")
                particao["subconjuntos"].append({"familias": familias, "ids_treino": amostra.id.tolist()})
                for nome, modelo in criar_modelos(42).items():
                    if nome not in ("Arvore", "Logistica"):
                        continue
                    modelo.fit(amostra[FEATURES], amostra.prioridade)
                    item = {"seed": seed, "fold": fold, "modelo": nome, "familias_treino": tamanho,
                            "registros_treino": len(amostra), "familias_validacao": len(familias_validacao),
                            "registros_validacao": len(validacao)}
                    for conjunto, df in (("treino", amostra), ("validacao", validacao)):
                        item.update({f"{conjunto}_{metrica}": valor for metrica, valor in
                                     metricas(df.prioridade, modelo.predict(df[FEATURES])).items()})
                    resultados.append(item)
            particoes.append(particao)
    resumos = agregar(resultados)
    relatorio = {
        "origem": "Somente chamados fictícios; rótulos derivados da política didática.",
        "protocolo": {"desenvolvimento_registros": len(desenvolvimento),
                      "desenvolvimento_familias": desenvolvimento.familia_cenario.nunique(),
                      "teste_reservado_usado": False, "ids_reservados_excluidos": reservado.id.tolist(),
                      "familias_reservadas_excluidas": sorted(familias_reservadas),
                      "validacao": "StratifiedGroupKFold de cinco folds repetido com sementes distintas, somente no desenvolvimento",
                      "seeds_particoes": seeds, "seed_modelos": 42, "quantidade_particoes": len(particoes),
                      "tamanhos_solicitados_familias": tamanhos,
                      "subamostragem": "Prefixos aninhados de ordem de famílias embaralhada por seed*100+fold; cobertura das duas classes no menor prefixo ajustada usando apenas o treino externo.",
                      "desvio_padrao": "Descritivo entre partições sobrepostas; não trata folds como amostras independentes nem representa incerteza em instituições reais."},
        "resumos": resumos, "resultados": resultados, "particoes": particoes,
        "discussao": [
            "A curva mede amostras de famílias fictícias, não necessidade de dados em uma instituição real.",
            "Um patamar ou desempenho perfeito não comprova que 120 registros bastem: a tarefa reproduz regras conhecidas e possui poucos tipos de cenário.",
            "Diferenças de treino e validação e dispersão entre famílias ajudam a identificar instabilidade; a curva pode não ser monotônica.",
            "O maior subconjunto da curva não usa todas as famílias de desenvolvimento, pois outras famílias precisam permanecer na validação externa."
        ],
        "hash_dados_numericos": hash_dados_numericos(dados), "versoes": versoes(),
    }
    relatorios = raiz / "relatorios"; relatorios.mkdir(parents=True, exist_ok=True)
    salvar_json(relatorios / "curva_aprendizado.json", relatorio)
    pd.DataFrame(resultados).to_csv(relatorios / "curva_aprendizado.csv", index=False)
    desenhar(resumos, relatorios / "figuras/curva_aprendizado.png")
    print("Curva de aprendizado concluída:", len(particoes), "partições;", len(resultados), "ajustes, sem teste reservado.")
    for nome in ("Arvore", "Logistica"):
        itens = [r for r in resumos if r["modelo"] == nome]
        for item in (itens[0], itens[-1]):
            print(nome, item["familias_treino"], "famílias - F2 validação:", item["validacao"]["f2"])
    return relatorio


if __name__ == "__main__":
    executar()
