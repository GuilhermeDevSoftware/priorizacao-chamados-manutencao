"""SQLite local, com parâmetros e conexão encerrada após cada requisição."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3

from flask import current_app, g

EQUIPES = ("TI", "Elétrica", "Hidráulica", "Triagem geral")
STATUS = ("Aberto", "Em atendimento", "Resolvido")
ROTULOS_PRIORIDADE = {0: "Não prioritário", 1: "Intermediário", 2: "Prioritário"}

# A coluna binária original continua no banco para manter as instalações anteriores.
PRIORIDADE_SUGERIDA_SQL = "COALESCE(prioridade_ia, 2 * prioridade_sugerida)"
PRIORIDADE_ATUAL_SQL = f"COALESCE(prioridade_manual, {PRIORIDADE_SUGERIDA_SQL})"

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

COLUNAS_TRIAGEM = {
    "prioridade_ia": "INTEGER CHECK(prioridade_ia IN (0,1,2))",
    "prioridade_manual": "INTEGER CHECK(prioridade_manual IN (0,1,2))",
    "classificacao_json": "TEXT",
}

SCHEMA_HISTORICO = """
CREATE TABLE IF NOT EXISTS chamado_alteracoes (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 chamado_id INTEGER NOT NULL REFERENCES chamados(id),
 responsavel TEXT NOT NULL,
 data TEXT NOT NULL,
 anterior_json TEXT NOT NULL,
 novo_json TEXT NOT NULL,
 motivo TEXT NOT NULL
)
"""


def inicializar(app):
    caminho = Path(app.config["DATABASE_PATH"])
    caminho.parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(caminho), timeout=5)) as conexao:
        with conexao:
            # Bloqueia outra inicialização até concluir os ALTER TABLE e índices.
            conexao.execute("BEGIN IMMEDIATE")
            for comando in SCHEMA.split(";"):
                if comando.strip():
                    conexao.execute(comando)
            colunas = {linha[1] for linha in conexao.execute("PRAGMA table_info(chamados)")}
            for nome, declaracao in COLUNAS_TRIAGEM.items():
                if nome not in colunas:
                    conexao.execute(f"ALTER TABLE chamados ADD COLUMN {nome} {declaracao}")
            conexao.execute(SCHEMA_HISTORICO)
            conexao.execute("CREATE INDEX IF NOT EXISTS chamado_alteracoes_chamado ON chamado_alteracoes(chamado_id, id DESC)")
            conexao.execute(
                f"CREATE INDEX IF NOT EXISTS chamados_fila ON chamados({PRIORIDADE_ATUAL_SQL} DESC, data_abertura, id) "
                "WHERE status <> 'Resolvido'"
            )
    app.teardown_appcontext(fechar)


def conectar():
    if "sqlite" not in g:
        g.sqlite = sqlite3.connect(str(current_app.config["DATABASE_PATH"]), timeout=5)
        g.sqlite.row_factory = sqlite3.Row
        g.sqlite.execute("PRAGMA foreign_keys = ON")
    return g.sqlite


def fechar(_erro=None):
    conexao = g.pop("sqlite", None)
    if conexao is not None:
        conexao.close()


def serializar(linha):
    registro = dict(linha)
    prioridade = registro.pop("prioridade_ia")
    if prioridade is None:
        prioridade = 2 * registro["prioridade_sugerida"]
    registro["prioridade_sugerida"] = prioridade
    manual = registro.pop("prioridade_manual")
    registro["prioridade_atual"] = prioridade if manual is None else manual
    registro["rotulo_prioridade"] = ROTULOS_PRIORIDADE[registro["prioridade_atual"]]
    registro["foto_url"] = f"api/chamados/{registro['id']}/foto" if registro["foto_caminho"] else None
    bruto = registro.pop("analise_json")
    registro["analise"] = json.loads(bruto) if bruto else None
    bruto = registro.pop("classificacao_json")
    registro["classificacao"] = json.loads(bruto) if bruto else None
    return registro


def historico_alteracoes(conexao, chamado_id):
    linhas = conexao.execute(
        "SELECT id, responsavel, data, anterior_json, novo_json, motivo "
        "FROM chamado_alteracoes WHERE chamado_id = ? ORDER BY id DESC",
        (chamado_id,),
    )
    alteracoes = []
    for linha in linhas:
        item = dict(linha)
        item["anterior"] = json.loads(item.pop("anterior_json"))
        item["novo"] = json.loads(item.pop("novo_json"))
        alteracoes.append(item)
    return alteracoes
