"""SQLite local, com parâmetros e conexão encerrada após cada requisição."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

from flask import current_app, g

EQUIPES = ("TI", "Elétrica", "Hidráulica", "Triagem geral")
STATUS = ("Aberto", "Em atendimento", "Resolvido")

SCHEMA = """
CREATE TABLE IF NOT EXISTS chamados (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 descricao TEXT NOT NULL,
 local TEXT NOT NULL,
 data_abertura TEXT NOT NULL,
 risco_seguranca INTEGER NOT NULL CHECK(risco_seguranca IN (0,1)),
 servico_essencial_interrompido INTEGER NOT NULL CHECK(servico_essencial_interrompido IN (0,1)),
 pessoas_afetadas INTEGER NOT NULL CHECK(pessoas_afetadas BETWEEN 0 AND 9007199254740991),
 dias_aguardando INTEGER NOT NULL CHECK(dias_aguardando BETWEEN 0 AND 9007199254740991),
 recorrente INTEGER NOT NULL CHECK(recorrente IN (0,1)),
 prioridade_sugerida INTEGER NOT NULL CHECK(prioridade_sugerida IN (0,1)),
 equipe_sugerida TEXT NOT NULL CHECK(equipe_sugerida IN ('TI','Elétrica','Hidráulica','Triagem geral')),
 justificativa_equipe TEXT NOT NULL,
 equipe_confirmada TEXT NOT NULL CHECK(equipe_confirmada IN ('TI','Elétrica','Hidráulica','Triagem geral')),
 status TEXT NOT NULL DEFAULT 'Aberto' CHECK(status IN ('Aberto','Em atendimento','Resolvido')),
 foto_caminho TEXT,
 analise_json TEXT
);
CREATE INDEX IF NOT EXISTS chamados_filtros ON chamados(equipe_confirmada, prioridade_sugerida, status);
"""


def inicializar(app):
    caminho = Path(app.config["DATABASE_PATH"])
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(caminho), timeout=5)) as conexao:
        with conexao:
            conexao.executescript(SCHEMA)
    app.teardown_appcontext(fechar)


def conectar():
    if "sqlite" not in g:
        g.sqlite = sqlite3.connect(str(current_app.config["DATABASE_PATH"]), timeout=5)
        g.sqlite.row_factory = sqlite3.Row
    return g.sqlite


def fechar(_erro=None):
    conexao = g.pop("sqlite", None)
    if conexao is not None:
        conexao.close()


def serializar(linha):
    registro = dict(linha)
    registro["rotulo_prioridade"] = "Prioritário" if registro["prioridade_sugerida"] else "Normal"
    registro["foto_url"] = f"api/chamados/{registro['id']}/foto" if registro["foto_caminho"] else None
    bruto = registro.pop("analise_json")
    registro["analise"] = json.loads(bruto) if bruto else None
    return registro
