"""Classificação textual experimental de equipe; nenhuma entrada altera a prioridade."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import json
import pickle
import re

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import FunctionTransformer

ROOT = Path(__file__).resolve().parent
EQUIPES_TEXTO = ['TI', 'Elétrica', 'Hidráulica', 'Triagem geral']
# Anotação editorial didática por família, anterior à medição de desempenho textual.
ROTULOS_POR_FAMILIA = {
    'macaneta_sala_vazia': ('Triagem geral', 'Ferragem de porta: manutenção predial fora das três especialidades.'),
    'pintura_corredor': ('Triagem geral', 'Pintura e acabamento predial.'),
    'lampada_deposito': ('Elétrica', 'Substituição ou diagnóstico de iluminação elétrica.'),
    'cadeira_estofado': ('Triagem geral', 'Mobiliário e estofamento.'),
    'projetor_reserva': ('TI', 'Equipamento audiovisual tratado como suporte de TI nesta taxonomia didática.'),
    'persiana_reuniao': ('Triagem geral', 'Reparo mecânico de persiana.'),
    'torneira_auxiliar': ('Hidráulica', 'Gotejamento em torneira e circuito de água.'),
    'impressora_secretaria': ('TI', 'Manutenção de periférico de informática.'),
    'ventilador_quadra': ('Elétrica', 'Equipamento elétrico de ventilação.'),
    'placa_identificacao': ('Triagem geral', 'Identificação e sinalização predial.'),
    'internet_leitura': ('TI', 'Conectividade de rede de dados.'),
    'laboratorio_tomadas': ('Elétrica', 'Circuito de tomadas elétricas.'),
    'som_auditorio': ('TI', 'Suporte audiovisual atribuído à TI nesta taxonomia.'),
    'banheiro_recorrente': ('Hidráulica', 'Regulagem de descarga sanitária.'),
    'porta_almoxarifado': ('Triagem geral', 'Ajuste mecânico de porta.'),
    'rede_oficina': ('TI', 'Oscilação da rede de dados da oficina.'),
    'fiacao_pouca_circulacao': ('Elétrica', 'Condutores elétricos expostos.'),
    'piso_escorregadio': ('Hidráulica', 'Correção do vazamento de água; isolamento do piso continua sendo decisão humana.'),
    'corrimao_escada': ('Triagem geral', 'Fixação de elemento estrutural de proteção.'),
    'porta_emergencia': ('Triagem geral', 'Desobstrução e funcionamento de saída de emergência.'),
    'forro_solto': ('Triagem geral', 'Fixação de elemento do forro.'),
    'vazamento_gas': ('Triagem geral', 'Gás exige profissional habilitado; a taxonomia não contém equipe específica.'),
    'falta_agua_escola': ('Hidráulica', 'Interrupção do abastecimento de água.'),
    'energia_ong': ('Elétrica', 'Interrupção de alimentação elétrica.'),
    'esgoto_interrompido': ('Hidráulica', 'Rede de esgoto e saneamento.'),
    'cozinha_sem_refrigeracao': ('Triagem geral', 'Refrigeração pode exigir especialidade não disponível; não presumir causa elétrica.'),
    'elevador_acessivel': ('Triagem geral', 'Elevador requer assistência especializada fora da taxonomia.'),
    'armario_auxiliar': ('Triagem geral', 'Reparo de fechadura e mobiliário.'),
    'acustica_oficina': ('Triagem geral', 'Acabamento de painel acústico.'),
    'computadores_auxiliares': ('TI', 'Equipamentos de informática.'),
}


def anotar_equipes(df):
    """Acrescenta apenas anotações; não muda entradas ou rótulos de prioridade."""
    resultado = df.copy()
    faltam = set(resultado.familia_cenario) - set(ROTULOS_POR_FAMILIA)
    if faltam:
        raise ValueError(f'Famílias sem anotação: {sorted(faltam)}')
    resultado['equipe_rotulo'] = resultado.familia_cenario.map(lambda f: ROTULOS_POR_FAMILIA[f][0])
    resultado['equipe_justificativa'] = resultado.familia_cenario.map(lambda f: ROTULOS_POR_FAMILIA[f][1])
    return resultado


def limpar_descricao(texto):
    """Remove o sufixo gerado com contagens e recorrência, sem observar o alvo."""
    return re.split(r'\s*Variação fictícia\s+\d+\s*:', str(texto), maxsplit=1, flags=re.I)[0].strip()


def limpar_lote(textos):
    return [limpar_descricao(t) for t in textos]


def criar_pipeline(seed=42):
    return Pipeline([
        ('limpeza', FunctionTransformer(limpar_lote, validate=False)),
        ('tfidf', FeatureUnion([
            ('palavras', TfidfVectorizer(strip_accents='unicode', lowercase=True, ngram_range=(1, 2))),
            ('caracteres', TfidfVectorizer(strip_accents='unicode', lowercase=True, analyzer='char_wb', ngram_range=(3, 5))),
        ])),
        ('classificador', LogisticRegression(C=1.0, max_iter=2000, random_state=seed)),
    ])


@lru_cache(maxsize=4)
def _carregar(caminho):
    # Somente artefato local do projeto, nunca upload ou URL fornecidos pelo visitante.
    return joblib.load(caminho)


def sugerir_equipe_texto(descricao, *, metadata_path=None, model_path=None):
    """Retorna sugestão somente quando o gate medido permitir; caso contrário None.

    O chamador mantém sua regra local quando este experimento não supera a regra,
    o artefato está ausente/incompatível ou sua saída é inválida.
    """
    metadata_path = Path(metadata_path or ROOT / 'modelo/equipe_texto_metadata.json')
    model_path = Path(model_path or ROOT / 'modelo/equipe_texto.joblib')
    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
        if metadata.get('habilitado_local') is not True:
            return None
        modelo = _carregar(str(model_path.resolve()))
        equipe = str(modelo.predict([descricao])[0])
        return equipe if equipe in EQUIPES_TEXTO else None
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError, EOFError, ImportError, pickle.UnpicklingError):
        return None
