"""Interpreta a árvore já publicada, sem retreinar nem sobrescrever o modelo."""
from __future__ import annotations

import hashlib
from itertools import product
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.tree import export_text, plot_tree

try:
    from .ml_comum import ROOT, FEATURES, politica, salvar_json, versoes
except ImportError:
    from ml_comum import ROOT, FEATURES, politica, salvar_json, versoes


LIMITES_POLITICA = {
    "risco_seguranca": (1,),
    "servico_essencial_interrompido": (1,),
    "pessoas_afetadas": (10, 40),
    "dias_aguardando": (7, 14),
    "recorrente": (1,),
}


def comparar_limiares(arvore):
    """Um corte real entre k-1 e k equivale a >= k para entradas inteiras."""
    linhas = []
    for no, indice in enumerate(arvore.tree_.feature):
        if indice < 0:
            continue
        campo = FEATURES[int(indice)]
        corte = float(arvore.tree_.threshold[no])
        inteiro_direita = int(np.floor(corte)) + 1
        limites = LIMITES_POLITICA[campo]
        correspondente = inteiro_direita if inteiro_direita in limites else None
        linhas.append({
            "no": int(no), "atributo": campo, "limiar_aprendido": corte,
            "primeiro_inteiro_ramo_direito": inteiro_direita,
            "condicao_ramo_direito": f"{campo} >= {inteiro_direita}",
            "limiar_politica_correspondente": correspondente,
            "equivalente_em_inteiros": correspondente is not None,
            "interpretacao": (
                "Corte intermediário entre inteiros consecutivos; mesma fronteira da política."
                if correspondente is not None else
                "Corte sem correspondência direta; examinar amostragem e caminho completo da árvore."
            ),
        })
    return linhas


def verificar_celulas(arvore):
    """Verifica células induzidas pelos cortes: seus representantes são sintéticos."""
    valores = {}
    for campo in FEATURES:
        if campo not in ("pessoas_afetadas", "dias_aguardando"):
            valores[campo] = [0, 1]
            continue
        limites = set(LIMITES_POLITICA[campo])
        for indice, corte in zip(arvore.tree_.feature, arvore.tree_.threshold):
            if indice >= 0 and FEATURES[int(indice)] == campo:
                limites.add(int(np.floor(corte)) + 1)
        pontos = {0, 9007199254740991}
        for limite in limites:
            pontos.update(max(0, limite + delta) for delta in (-1, 0, 1))
        valores[campo] = sorted(pontos)
    representantes = pd.DataFrame(product(*(valores[f] for f in FEATURES)), columns=FEATURES)
    esperado = politica(representantes)
    previsto = arvore.predict(representantes)
    return {"representantes": len(representantes),
            "divergencias": int(np.count_nonzero(esperado != previsto)),
            "natureza": "Verificação de consistência em representantes das células dos cortes; não validação externa."}


def executar(raiz=ROOT):
    raiz = Path(raiz)
    diretorio = raiz / "relatorios"
    figuras = diretorio / "figuras"
    figuras.mkdir(parents=True, exist_ok=True)
    caminho = raiz / "modelo" / "arvore.joblib"
    arvore = joblib.load(caminho)
    texto = export_text(arvore, feature_names=FEATURES, decimals=2)
    (diretorio / "arvore_interpretada.txt").write_text(texto, encoding="utf-8")
    limiares = comparar_limiares(arvore)
    pd.DataFrame(limiares).to_csv(diretorio / "limiares_arvore.csv", index=False)
    importancia = [{"atributo": campo, "importancia": float(valor)}
                   for campo, valor in zip(FEATURES, arvore.feature_importances_)]
    pd.DataFrame(importancia).to_csv(diretorio / "importancias_arvore.csv", index=False)
    fig, ax = plt.subplots(figsize=(22, 11))
    plot_tree(arvore, feature_names=FEATURES, class_names=["Normal", "Prioritário"],
              filled=True, rounded=True, precision=2, impurity=True, fontsize=9, ax=ax)
    for anotacao in ax.texts:
        texto_no = anotacao.get_text()
        for original, traduzido in (("gini =", "impureza ="), ("samples =", "amostras ="),
                                    ("value =", "contagens ="), ("class =", "classe ="),
                                    ("True", "Sim"), ("False", "Não")):
            texto_no = texto_no.replace(original, traduzido)
        anotacao.set_text(texto_no)
    ax.set_title("Árvore publicada: campos confirmados → prioridade (dados fictícios)", fontsize=16)
    fig.tight_layout()
    fig.savefig(figuras / "arvore_publicada.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    ordenadas = sorted(importancia, key=lambda item: item["importancia"])
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.barh([r["atributo"] for r in ordenadas], [r["importancia"] for r in ordenadas], color="#267466")
    ax.set_xlabel("Redução normalizada de impureza no treino")
    ax.set_title("Importância dos atributos da árvore publicada")
    fig.tight_layout()
    fig.savefig(figuras / "importancias_arvore.png", dpi=180, bbox_inches="tight")
    plt.close(fig)
    consistencia = verificar_celulas(arvore)
    equivalentes = all(item["equivalente_em_inteiros"] for item in limiares)
    resultados = {
        "origem": "Dados inteiramente fictícios; modelo publicado preservado.",
        "modelo_sha256": hashlib.sha256(caminho.read_bytes()).hexdigest(),
        "profundidade": int(arvore.get_depth()), "nos": int(arvore.tree_.node_count),
        "amostras_treino": int(arvore.tree_.n_node_samples[0]),
        "importancias": importancia, "limiares": limiares,
        "consistencia_celulas": consistencia,
        "recuperou_fronteiras_politica": equivalentes and consistencia["divergencias"] == 0,
        "interpretacao": (
            "A árvore recuperou a política nos domínios inteiros verificados. Os cortes 39,5/6,5 e "
            "9,5/13,5 equivalem a pessoas >= 40 e dias >= 7, ou pessoas >= 10 e dias >= 14; "
            "0,5 separa os indicadores 0/1. A ordem dos testes reorganiza a expressão lógica. "
            "Não se trata de descoberta de critérios reais: os rótulos foram gerados pela própria política."
            if equivalentes and consistencia["divergencias"] == 0 else
            "Há cortes ou decisões diferentes da política; a tabela e os representantes mostram as diferenças observadas."
        ),
        "limites": [
            "Cortes intermediários são equivalentes para inteiros consecutivos; outras amostras podem gerar cortes diferentes em lacunas sem exemplos.",
            "Importância por redução de impureza descreve este ajuste e pode favorecer variáveis com mais cortes; não demonstra causalidade.",
            "A ordem e a frequência dos atributos refletem a base pequena e a distribuição artificial dos cenários.",
            "Verificações derivadas da política medem consistência, não desempenho em manutenção real.",
        ], "versoes": versoes(),
    }
    salvar_json(diretorio / "interpretabilidade.json", resultados)
    print("Interpretação exportada; divergências nas células:", consistencia["divergencias"])
    return resultados


if __name__ == "__main__":
    executar()
