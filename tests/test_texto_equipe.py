"""Avaliação e fallback textual local sem rede ou alteração da prioridade."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import joblib
import pandas as pd
import pytest

from app import create_app
from scripts.ml_comum import FEATURES, ROOT, divisao_original, hash_dados_numericos
from scripts.treinar_texto import executar, prever_regra, superou_regra
from texto_equipe import anotar_equipes, criar_pipeline, limpar_descricao, sugerir_equipe_texto


def test_rotulagem_manual_nao_altera_atributos_originais():
    df=pd.read_csv(ROOT/'dados/chamados_ficticios.csv')
    original=df.drop(columns=['equipe_rotulo','equipe_justificativa'],errors='ignore')
    anotado=anotar_equipes(original)
    pd.testing.assert_frame_equal(anotado[original.columns],original)
    assert hash_dados_numericos(anotado)==hash_dados_numericos(original)
    assert anotado.groupby('familia_cenario').equipe_rotulo.nunique().eq(1).all()
    assert anotado.loc[anotado.familia_cenario.isin(['vazamento_gas','cozinha_sem_refrigeracao','elevador_acessivel']),'equipe_rotulo'].eq('Triagem geral').all()


def test_limpeza_remove_contagens_geradas_sem_usar_prioridade():
    assert limpar_descricao('Computador com falha. Variação fictícia 2: 200 pessoa(s), 30 dia(s).')=='Computador com falha.'
    assert limpar_descricao('Impressora desconectada.')=='Impressora desconectada.'


@pytest.mark.parametrize('a,f,esperado',[(.8,.8,True),(.75,.8,False),(.8,.7,False),(.75,.7,False)])
def test_gate_exige_superar_ambas_metricas(a,f,esperado):
    modelos={'TFIDF_Logistica':{'acuracia':{'media':a},'f1_macro':{'media':f}},
             'Regra_local':{'acuracia':{'media':.75},'f1_macro':{'media':.7}}}
    assert superou_regra(modelos)==esperado


def test_script_reproduz_avaliacao_agrupada_sem_teste_na_selecao(tmp_path):
    pasta=tmp_path/'dados';pasta.mkdir()
    df=pd.read_csv(ROOT/'dados/chamados_ficticios.csv')
    df.to_csv(pasta/'chamados_ficticios.csv',index=False)
    resultado=executar(tmp_path,repeticoes=2)
    salvo=json.loads((tmp_path/'relatorios/classificador_texto.json').read_text())
    assert salvo==resultado
    assert salvo['protocolo']['teste_reservado_usado_na_selecao'] is False
    oof=pd.read_csv(tmp_path/'relatorios/classificador_texto_oof.csv')
    desenvolvimento,reservado=divisao_original(df)
    assert set(oof.id)==set(df.iloc[desenvolvimento].id)
    assert not set(oof.id)&set(df.iloc[reservado].id)
    assert len(oof)==2*len(desenvolvimento)
    metadata=json.loads((tmp_path/'modelo/equipe_texto_metadata.json').read_text())
    assert set(metadata['ids_treino'])==set(df.iloc[desenvolvimento].id)
    assert not set(metadata['ids_treino'])&set(df.iloc[reservado].id)
    assert len(metadata['familias_treino'])==24
    assert salvo['gate']['habilitado_local']==superou_regra(salvo['modelos'])
    for nome in ['TFIDF_Logistica','Regra_local']:
        matriz=salvo['modelos'][nome]['matriz_confusao_oof_somada']
        assert sum(sum(linha) for linha in matriz)==len(oof)


def test_modelo_inativo_nao_e_carregado(tmp_path):
    meta=tmp_path/'meta.json';meta.write_text(json.dumps({'habilitado_local':False}))
    with patch('texto_equipe.joblib.load') as carregar:
        assert sugerir_equipe_texto('Computador com falha',metadata_path=meta,model_path=tmp_path/'nao-existe.joblib') is None
    carregar.assert_not_called()


def test_modelo_ausente_ou_invalido_mantem_fallback(tmp_path):
    meta=tmp_path/'meta.json';meta.write_text(json.dumps({'habilitado_local':True}))
    assert sugerir_equipe_texto('Torneira quebrada',metadata_path=meta,model_path=tmp_path/'ausente.joblib') is None
    ruim=tmp_path/'invalido.joblib';ruim.write_bytes(b'arquivo invalido')
    assert sugerir_equipe_texto('Torneira quebrada',metadata_path=meta,model_path=ruim) is None


def test_modelo_experimental_validado_pode_prever_quando_gate_ativado(tmp_path):
    # Modelo de teste pequeno, sem contaminar o artefato ou o gate reais.
    modelo=criar_pipeline().fit(['Computador defeituoso','Tomada quebrada','Torneira quebrada','Porta presa'],['TI','Elétrica','Hidráulica','Triagem geral'])
    caminho=tmp_path/'teste.joblib';joblib.dump(modelo,caminho)
    meta=tmp_path/'meta.json';meta.write_text(json.dumps({'habilitado_local':True}))
    assert sugerir_equipe_texto('Computador defeituoso',metadata_path=meta,model_path=caminho)=='TI'


def test_rota_preserva_regra_quando_experimento_nao_supera_e_nao_chama_rede(tmp_path):
    metadata=json.loads((ROOT/'modelo/equipe_texto_metadata.json').read_text())
    assert metadata['habilitado_local'] is False
    aplicacao=create_app({'TESTING':True,'OPENAI_API_KEY':'','DATABASE_PATH':str(tmp_path/'chamados.sqlite3'),'UPLOAD_FOLDER':str(tmp_path/'uploads')})
    with patch('app.requests.post') as rede, aplicacao.test_client() as cliente:
        resposta=cliente.post('/api/analisar',data={'descricao':'Computador com defeito.'},content_type='multipart/form-data')
        assert resposta.status_code==200
        assert resposta.json['origem']=='regra_local'
        assert resposta.json['equipe_sugerida']=='TI'
        assert all(v is None for v in resposta.json['campos'].values())
        assert resposta.json['confirmacao_necessaria'] is True
        resposta_prioridade=cliente.post('/api/prever',json=dict(zip(FEATURES,[0,0,0,0,0])))
        assert resposta_prioridade.json['classe']==0
    rede.assert_not_called()
