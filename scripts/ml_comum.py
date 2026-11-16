"""Ferramentas reproduzíveis dos experimentos; sem modificar a árvore do aplicativo."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import platform

import numpy as np
import pandas as pd
import sklearn
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, fbeta_score, precision_score, recall_score
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ["risco_seguranca", "servico_essencial_interrompido", "pessoas_afetadas", "dias_aguardando", "recorrente"]
METRICAS = ["sensibilidade", "precisao", "f1", "f2", "acuracia"]


def politica(X):
    """Política conhecida que produziu os rótulos fictícios: baseline determinístico."""
    a = X[FEATURES].to_numpy() if isinstance(X, pd.DataFrame) else np.asarray(X)
    return ((a[:, 0] == 1) | (a[:, 1] == 1) | ((a[:, 2] >= 40) & (a[:, 3] >= 7)) |
            ((a[:, 4] == 1) & (a[:, 2] >= 10) & (a[:, 3] >= 14))).astype(int)


class RegrasPolitica(ClassifierMixin, BaseEstimator):
    """Baseline sem parâmetros aprendidos; y é deliberadamente ignorado no fit."""
    def fit(self, X, y=None):
        self.classes_ = np.array([0, 1])
        self.n_features_in_ = len(FEATURES)
        return self

    def predict(self, X):
        return politica(X)


def criar_modelos(seed=42):
    return {
        "Dummy": DummyClassifier(strategy="most_frequent"),
        "Regras": RegrasPolitica(),
        "Arvore": DecisionTreeClassifier(max_depth=6, random_state=seed),
        "Logistica": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=seed)),
        "RandomForest": RandomForestClassifier(n_estimators=100, random_state=seed, n_jobs=1),
    }


def carregar_dados(raiz=ROOT):
    df = pd.read_csv(Path(raiz) / "dados/chamados_ficticios.csv")
    obrigatorias = {"id", "familia_cenario", "descricao", "prioridade", *FEATURES}
    if not obrigatorias <= set(df):
        raise ValueError("Base sem os campos obrigatórios do experimento.")
    if df[list(obrigatorias)].isna().any().any() or not df.id.is_unique:
        raise ValueError("Valores ausentes ou IDs repetidos.")
    for campo in FEATURES + ["prioridade"]:
        if not pd.api.types.is_integer_dtype(df[campo]) or (df[campo] < 0).any():
            raise ValueError(f"Campo numérico inválido: {campo}")
    for campo in [FEATURES[0], FEATURES[1], FEATURES[4], "prioridade"]:
        if not set(df[campo]) <= {0, 1}:
            raise ValueError(f"Campo binário inválido: {campo}")
    if not np.array_equal(politica(df), df.prioridade.to_numpy()):
        raise ValueError("Os rótulos limpos não correspondem à política declarada.")
    return df.reset_index(drop=True)


def divisao_original(df):
    cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    treino, teste = next(cv.split(df[FEATURES], df.prioridade, df.familia_cenario))
    if set(df.iloc[treino].familia_cenario) & set(df.iloc[teste].familia_cenario):
        raise AssertionError("Vazamento entre famílias.")
    return treino, teste


def metricas(y, pred):
    return {
        "sensibilidade": float(recall_score(y, pred, pos_label=1, zero_division=0)),
        "precisao": float(precision_score(y, pred, pos_label=1, zero_division=0)),
        "f1": float(f1_score(y, pred, pos_label=1, zero_division=0)),
        "f2": float(fbeta_score(y, pred, beta=2, pos_label=1, zero_division=0)),
        "acuracia": float(accuracy_score(y, pred)),
    }


def salvar_json(caminho, obj):
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    def converter(valor):
        if isinstance(valor, np.generic):
            return valor.item()
        if isinstance(valor, np.ndarray):
            return valor.tolist()
        if isinstance(valor, Path):
            return str(valor)
        raise TypeError(type(valor).__name__)
    caminho.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False, default=converter) + "\n", encoding="utf-8")


def hash_dados_numericos(df):
    """Não depende da futura anotação textual de equipe nem de colunas documentais."""
    texto = df[["id", "familia_cenario", *FEATURES, "prioridade"]].to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def versoes():
    return {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scikit_learn": sklearn.__version__}
