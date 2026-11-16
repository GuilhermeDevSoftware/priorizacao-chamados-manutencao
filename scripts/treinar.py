"""Geração, treino e avaliação reproduzíveis. Dados inteiramente fictícios.
Autor: Guilherme Costa — Engenharia de Computação.
Execute a partir da raiz: python scripts/treinar.py
"""
# %% importacoes
from pathlib import Path
import json
import platform
import os
import sys
import hashlib
import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.dummy import DummyClassifier
from sklearn.model_selection import StratifiedGroupKFold, GridSearchCV
from sklearn.metrics import (accuracy_score, recall_score, precision_score,
                             confusion_matrix, make_scorer, fbeta_score)

FEATURES = ["risco_seguranca", "servico_essencial_interrompido", "pessoas_afetadas",
            "dias_aguardando", "recorrente"]
SEMENTE = 42
ORIGEM = "Base inteiramente fictícia, criada para demonstração acadêmica; nenhum chamado real."

# %% politica
POLITICA = """Política didática definida ANTES do treino: prioritário (1) se houver
risco à segurança OU interrupção de serviço essencial OU (pelo menos 40 pessoas
afetadas E pelo menos 7 dias de espera) OU (recorrência E pelo menos 10 pessoas
afetadas E pelo menos 14 dias de espera). Nos demais casos, normal (0).
Segurança independe do número de pessoas: fiação exposta em local pouco usado
continua prioritária. Os limiares de espera/impacto são escolhas pedagógicas,
não padrões técnicos universais. Em uso real devem ser pactuados com a instituição.
Serviço essencial significa indisponibilidade de água, energia, saneamento,
alimentação ou acesso indispensável; equipamento auxiliar com alternativa não
é automaticamente essencial. O responsável sempre revisa a sugestão."""


def rotular(valores):
    risco, essencial, pessoas, dias, recorrente = valores
    motivos = []
    if risco:
        motivos.append("Risco à segurança, mesmo com pouca circulação")
    if essencial:
        motivos.append("Serviço essencial interrompido")
    if pessoas >= 40 and dias >= 7:
        motivos.append("Impacto em pelo menos 40 pessoas e espera de pelo menos 7 dias")
    if recorrente and pessoas >= 10 and dias >= 14:
        motivos.append("Recorrência, pelo menos 10 pessoas e espera de pelo menos 14 dias")
    return int(bool(motivos)), "; ".join(motivos) or "Baixo impacto segundo a política didática"

# %% dados

def gerar_base():
    # Cada família reúne quatro variações do MESMO tipo de cenário. Tuplas em FEATURES.
    cenarios = [
        ("macaneta_sala_vazia", "Maçaneta frouxa em sala desocupada, sem risco de aprisionamento", [(0,0,0,0,0),(0,0,0,2,0),(0,0,0,9,1),(0,0,0,20,1)]),
        ("pintura_corredor", "Pintura descascada sem umidade ou risco no corredor", [(0,0,2,3,0),(0,0,5,10,0),(0,0,10,25,0),(0,0,20,30,0)]),
        ("lampada_deposito", "Lâmpada de depósito falhou; iluminação alternativa suficiente", [(0,0,1,1,0),(0,0,2,4,0),(0,0,4,8,0),(0,0,0,18,1)]),
        ("cadeira_estofado", "Estofado rasgado de cadeira retirada de uso, estrutura íntegra", [(0,0,1,0,0),(0,0,3,2,0),(0,0,2,15,0),(0,0,5,25,1)]),
        ("projetor_reserva", "Projetor auxiliar sem imagem; existe equipamento substituto", [(0,0,0,2,0),(0,0,12,3,1),(0,0,20,5,0),(0,0,25,6,1)]),
        ("persiana_reuniao", "Persiana travada na sala de reunião, sem peças soltas", [(0,0,4,2,0),(0,0,6,7,0),(0,0,8,15,0),(0,0,12,10,1)]),
        ("torneira_auxiliar", "Torneira auxiliar com gotejamento; outras pias disponíveis", [(0,0,3,1,0),(0,0,5,4,1),(0,0,8,15,1),(0,0,9,25,1)]),
        ("impressora_secretaria", "Impressora administrativa indisponível, com alternativa", [(0,0,4,0,0),(0,0,8,6,1),(0,0,10,13,1),(0,0,15,20,0)]),
        ("ventilador_quadra", "Ventilador auxiliar da quadra falhou, ambiente ventilado", [(0,0,15,3,0),(0,0,20,7,0),(0,0,30,9,0),(0,0,35,12,0)]),
        ("placa_identificacao", "Placa de identificação apagada; sinalização de emergência íntegra", [(0,0,5,5,0),(0,0,10,7,0),(0,0,20,10,0),(0,0,39,20,0)]),
        ("internet_leitura", "Rede auxiliar da sala de leitura falhou; atividades essenciais continuam", [(0,0,39,6,0),(0,0,40,6,0),(0,0,41,7,0),(0,0,60,10,0)]),
        ("laboratorio_tomadas", "Tomadas auxiliares desativadas com segurança no laboratório", [(0,0,35,7,0),(0,0,40,7,0),(0,0,45,6,0),(0,0,50,8,0)]),
        ("som_auditorio", "Som auxiliar do auditório falhou, sem interromper serviço essencial", [(0,0,40,6,0),(0,0,40,7,0),(0,0,80,8,1),(0,0,39,8,0)]),
        ("banheiro_recorrente", "Descarga auxiliar requer regulagem recorrente; demais banheiros disponíveis", [(0,0,9,14,1),(0,0,10,14,1),(0,0,10,13,1),(0,0,11,15,1)]),
        ("porta_almoxarifado", "Porta interna arrasta no piso, sem bloquear saída ou acesso essencial", [(0,0,9,13,1),(0,0,10,14,1),(0,0,12,15,1),(0,0,15,16,1)]),
        ("rede_oficina", "Rede auxiliar de oficina oscila repetidamente, com alternativa disponível", [(0,0,10,13,1),(0,0,10,14,1),(0,0,20,14,0),(0,0,20,14,1)]),
        ("fiacao_pouca_circulacao", "Fiação exposta em área de pouca circulação: possível choque elétrico", [(1,0,0,0,0),(1,0,1,0,0),(1,0,2,1,1),(1,0,3,5,0)]),
        ("piso_escorregadio", "Vazamento deixa piso de circulação escorregadio", [(1,0,5,0,0),(1,0,20,1,0),(1,0,40,2,1),(1,0,80,3,1)]),
        ("corrimao_escada", "Corrimão solto em escada utilizada por pessoas", [(1,0,2,0,0),(1,0,15,2,0),(1,0,50,6,1),(1,0,100,8,1)]),
        ("porta_emergencia", "Porta de saída de emergência obstruída", [(1,0,0,0,0),(1,0,30,1,0),(1,0,70,2,1),(1,0,150,3,0)]),
        ("forro_solto", "Placa do forro solta com risco de queda", [(1,0,0,1,0),(1,0,4,2,0),(1,0,20,4,1),(1,0,45,10,1)]),
        ("vazamento_gas", "Odor de gás em cozinha, uso suspenso e área isolada", [(1,1,5,0,0),(1,1,20,0,1),(1,1,80,1,0),(1,1,120,2,1)]),
        ("falta_agua_escola", "Falta de água na escola, impedindo higiene e funcionamento", [(0,1,30,0,0),(0,1,100,1,0),(0,1,200,2,1),(0,1,350,4,1)]),
        ("energia_ong", "Falta de energia interrompe atendimento essencial da ONG", [(0,1,8,0,0),(0,1,20,1,1),(0,1,50,3,0),(0,1,90,7,1)]),
        ("esgoto_interrompido", "Saneamento indisponível e sanitários essenciais interditados", [(1,1,10,0,0),(1,1,25,1,0),(1,1,60,3,1),(1,1,180,5,1)]),
        ("cozinha_sem_refrigeracao", "Refrigeração da alimentação institucional interrompida", [(0,1,15,0,0),(0,1,40,1,0),(0,1,90,2,1),(0,1,220,6,1)]),
        ("elevador_acessivel", "Único acesso acessível aos serviços essenciais está indisponível", [(0,1,1,0,0),(0,1,2,1,1),(0,1,6,4,0),(0,1,12,10,1)]),
        ("armario_auxiliar", "Fechadura de armário auxiliar falha, sem itens essenciais retidos", [(0,0,2,30,1),(0,0,9,14,1),(0,0,10,14,1),(0,0,11,20,1)]),
        ("acustica_oficina", "Painel acústico requer reparo estético, firmemente preso", [(0,0,39,7,0),(0,0,40,7,0),(0,0,41,6,1),(0,0,42,8,1)]),
        ("computadores_auxiliares", "Computadores auxiliares indisponíveis, atendimento essencial mantido", [(0,0,9,20,1),(0,0,10,20,1),(0,0,30,13,1),(0,0,30,14,1)]),
    ]
    registros = []
    for familia, descricao, variacoes in cenarios:
        for i, valores in enumerate(variacoes, start=1):
            classe, justificativa = rotular(valores)
            registros.append({"id": f"FIC-{len(registros)+1:03d}",
                "familia_cenario": familia,
                "descricao": f"{descricao}. Variação fictícia {i}: {valores[2]} pessoa(s) afetada(s), {valores[3]} dia(s) de espera; recorrência {'sim' if valores[4] else 'não'}.",
                **dict(zip(FEATURES, valores)), "prioridade": classe,
                "justificativa_rotulo": justificativa, "origem": "fictícia"})
    # A anotação de equipe é documental: não participa do treino de prioridade.
    raiz_projeto = str(Path(__file__).resolve().parents[1])
    if raiz_projeto not in sys.path:
        sys.path.insert(0, raiz_projeto)
    from texto_equipe import anotar_equipes
    return anotar_equipes(pd.DataFrame(registros))

# %% validacao

def validar_base(df):
    assert len(df) == 120, "São esperados 120 chamados fictícios"
    assert df["id"].is_unique and not df.isna().any().any()
    assert df["familia_cenario"].nunique() == 30
    assert df.groupby("familia_cenario").size().eq(4).all()
    for campo in FEATURES + ["prioridade"]:
        assert pd.api.types.is_integer_dtype(df[campo]), campo
        assert (df[campo] >= 0).all(), campo
    for campo in ["risco_seguranca", "servico_essencial_interrompido", "recorrente", "prioridade"]:
        assert set(df[campo].unique()) <= {0, 1}, campo
    assert set(df["prioridade"].unique()) == {0, 1}
    assert df["origem"].eq("fictícia").all()
    assert all(rotular(row)[0] == alvo for row, alvo in zip(df[FEATURES].to_numpy(), df.prioridade))
    return {"registros": len(df), "familias": int(df.familia_cenario.nunique()),
            "classes": {str(k):int(v) for k,v in df.prioridade.value_counts().sort_index().items()}}

# %% treino

def treinar(df):
    X, y, grupos = df[FEATURES], df["prioridade"], df["familia_cenario"]
    # Primeira partição pré-fixada; nenhuma escolha por desempenho no teste.
    externo = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEMENTE)
    indices_treino, indices_teste = next(externo.split(X, y, grupos))
    assert not set(grupos.iloc[indices_treino]) & set(grupos.iloc[indices_teste])
    X_treino, y_treino = X.iloc[indices_treino], y.iloc[indices_treino]
    X_teste, y_teste = X.iloc[indices_teste], y.iloc[indices_teste]
    interno = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEMENTE)
    busca = GridSearchCV(DecisionTreeClassifier(random_state=SEMENTE),
        {"max_depth": [1, 2, 3, 4, 5, 6, None]}, cv=interno,
        scoring={"f2": make_scorer(fbeta_score, beta=2, zero_division=0),
                 "sensibilidade": make_scorer(recall_score, zero_division=0),
                 "precisao": make_scorer(precision_score, zero_division=0)},
        refit="f2", error_score="raise", n_jobs=1)
    # F2 dá peso maior à sensibilidade. Empate: primeiro candidato, árvore menos profunda.
    busca.fit(X_treino, y_treino, groups=grupos.iloc[indices_treino])
    arvore = busca.best_estimator_
    baseline = DummyClassifier(strategy="most_frequent")
    baseline.fit(X_treino, y_treino)
    return arvore, baseline, busca, indices_treino, indices_teste

# %% avaliacao

def calcular_metricas(y, predito):
    return {"sensibilidade_prioritaria": float(recall_score(y, predito, pos_label=1, zero_division=0)),
            "precisao_prioritaria": float(precision_score(y, predito, pos_label=1, zero_division=0)),
            "acuracia": float(accuracy_score(y, predito)),
            "matriz_confusao": confusion_matrix(y, predito, labels=[0,1]).tolist(),
            "ordem_classes_matriz": [0,1], "linhas": "real", "colunas": "prevista"}


def avaliar(df, arvore, baseline, busca, indices_treino, indices_teste):
    teste = df.iloc[indices_teste].copy()
    teste["previsto_arvore"] = arvore.predict(teste[FEATURES])
    teste["previsto_baseline"] = baseline.predict(teste[FEATURES])
    fn = teste.loc[(teste.prioridade == 1) & (teste.previsto_arvore == 0),
                   ["id", "familia_cenario", "descricao", *FEATURES, "prioridade", "previsto_arvore"]]
    proporcoes = {}
    for nome, ids in [("base", df.index), ("treino", indices_treino), ("teste", indices_teste)]:
        conjunto = df.loc[ids]
        proporcoes[nome] = {"registros": len(conjunto), "familias": int(conjunto.familia_cenario.nunique()),
            "classes": {str(k): int(v) for k,v in conjunto.prioridade.value_counts().sort_index().items()},
            "proporcao_prioritaria": float(conjunto.prioridade.mean())}
    cv = []
    for pos, parametros in enumerate(busca.cv_results_["params"]):
        cv.append({"max_depth": parametros["max_depth"],
                   "f2_medio": float(busca.cv_results_["mean_test_f2"][pos]),
                   "sensibilidade_media": float(busca.cv_results_["mean_test_sensibilidade"][pos]),
                   "precisao_media": float(busca.cv_results_["mean_test_precisao"][pos])})
    metricas = {"origem": ORIGEM, "semente": SEMENTE, "avaliacao_em": "Google Colab" if ("google.colab" in sys.modules or "COLAB_RELEASE_TAG" in os.environ) else "Ambiente local (Python/nbclient)",
        "politica_rotulos": POLITICA, "divisao": proporcoes,
        "separacao_grupos": "StratifiedGroupKFold 5 folds, primeira partição fixa; famílias disjuntas",
        "ajuste": {"metodo": "GridSearchCV com StratifiedGroupKFold 4 folds exclusivamente no treino", "criterio": "F2 da classe 1; empate favorece menor profundidade", "melhor_max_depth": busca.best_params_["max_depth"], "profundidade_aprendida": arvore.get_depth(), "validacao_cruzada": cv},
        "arvore": calcular_metricas(teste.prioridade, teste.previsto_arvore),
        "baseline_maioria": calcular_metricas(teste.prioridade, teste.previsto_baseline),
        "classe_majoritaria_treino": int(baseline.predict(df.iloc[indices_teste][FEATURES])[0]),
        "falsos_negativos": fn.to_dict(orient="records"),
        "versoes": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scikit_learn": sklearn.__version__, "joblib": joblib.__version__},
        "limites": ["Teste pequeno e fictício: métricas não estimam desempenho em instituições reais.", "Rótulos derivados de uma política explícita: o modelo aproxima regras escolhidas, sem descoberta de risco real.", "Famílias separadas reduzem vazamento de variações; padrões de atributos podem se repetir entre famílias.", "Ausência de falsos negativos neste teste, se observada, não garante segurança fora da amostra.", "Nenhuma previsão substitui inspeção técnica, resposta a emergências ou decisão do responsável."]}
    return metricas, teste

# %% exportacao

def exportar(raiz, df, arvore, baseline, busca, indices_treino, indices_teste, metricas, teste):
    raiz = Path(raiz)
    for pasta in ["dados", "modelo", "relatorios"]:
        (raiz / pasta).mkdir(parents=True, exist_ok=True)
    csv = df.to_csv(index=False, lineterminator="\n")
    (raiz / "dados/chamados_ficticios.csv").write_text(csv, encoding="utf-8")
    arv = arvore.tree_
    nos = []
    for i in range(arv.node_count):
        # O valor do sklearn pode ser proporção; escalamos pelas amostras ponderadas.
        contagens = (arv.value[i][0] / arv.value[i][0].sum() * arv.weighted_n_node_samples[i]).tolist()
        nos.append({"id": i, "feature_index": int(arv.feature[i]),
            "threshold": float(arv.threshold[i]), "left": int(arv.children_left[i]),
            "right": int(arv.children_right[i]), "counts": [float(v) for v in contagens],
            "prediction": int(arvore.classes_[int(np.argmax(arv.value[i][0]))])})
    modelo = {"schema_version": 1, "model_type": "DecisionTreeClassifier", "root": 0,
        "feature_order": FEATURES, "classes": [int(v) for v in arvore.classes_],
        "class_labels": {"0": "Normal", "1": "Prioritário"},
        "comparison": "left if float32(value) <= threshold; otherwise right",
        "nodes": nos, "metadata": {"origem": ORIGEM, "autor": "Guilherme Costa",
            "semente": SEMENTE, "max_depth": busca.best_params_["max_depth"],
            "sklearn_version": sklearn.__version__, "data_sha256": hashlib.sha256(csv.encode()).hexdigest(),
            "uso": "Demonstração acadêmica com revisão humana obrigatória", "limites_entrada": {"pessoas_afetadas": [0, 9007199254740991], "dias_aguardando": [0, 9007199254740991]}}}
    (raiz / "modelo/arvore.json").write_text(json.dumps(modelo, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (raiz / "modelo/regras_arvore.txt").write_text(export_text(arvore, feature_names=FEATURES), encoding="utf-8")
    joblib.dump(arvore, raiz / "modelo/arvore.joblib")
    divisao = df[["id", "familia_cenario", "prioridade"]].copy()
    divisao["conjunto"] = "treino"
    divisao.loc[indices_teste, "conjunto"] = "teste"
    divisao.to_csv(raiz / "dados/divisao_treino_teste.csv", index=False)
    teste.to_csv(raiz / "relatorios/predicoes_teste.csv", index=False)
    (raiz / "relatorios/metricas.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return modelo

# %% execucao

def executar(raiz="."):
    df = gerar_base()
    print(ORIGEM)
    print("Validação:", validar_base(df))
    arvore, baseline, busca, indices_treino, indices_teste = treinar(df)
    metricas, teste = avaliar(df, arvore, baseline, busca, indices_treino, indices_teste)
    modelo = exportar(raiz, df, arvore, baseline, busca, indices_treino, indices_teste, metricas, teste)
    print("Divisão:", json.dumps(metricas["divisao"], ensure_ascii=False))
    print("Melhor profundidade:", busca.best_params_["max_depth"])
    print("Árvore:", json.dumps(metricas["arvore"], ensure_ascii=False))
    print("Baseline:", json.dumps(metricas["baseline_maioria"], ensure_ascii=False))
    print("Falsos negativos:", len(metricas["falsos_negativos"]))
    return df, arvore, baseline, busca, indices_treino, indices_teste, metricas, teste, modelo


if __name__ == "__main__":
    executar(Path(__file__).resolve().parents[1])
