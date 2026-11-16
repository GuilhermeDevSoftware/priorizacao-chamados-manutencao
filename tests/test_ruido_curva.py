"""Invariantes do experimento: nenhuma corrupção do teste ou dos dados originais."""
import sys
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from experimento_ruido import executar, gerar_ruido, pesos_fronteira
from ml_comum import carregar_dados, divisao_original, politica


def test_ruido_tem_mesmo_orcamento_e_preserva_entradas():
    df=carregar_dados(); treino,teste=divisao_original(df)
    original=df.copy(deep=True); X=df.iloc[treino]; y=X.prioridade.to_numpy().copy()
    for modo in ("uniforme","fronteira"):
        corrompido,ids=gerar_ruido(X,y,.2,42,modo)
        assert len(ids)==round(.2*len(treino))
        assert np.count_nonzero(corrompido!=y)==len(ids)
        assert np.array_equal(y,X.prioridade)
        assert set(X.iloc[ids].id).isdisjoint(df.iloc[teste].id)
        if modo=="fronteira":
            assert X.iloc[ids].risco_seguranca.eq(0).all()
            assert X.iloc[ids].servico_essencial_interrompido.eq(0).all()
    pd.testing.assert_frame_equal(df,original)


def test_pesos_privilegiam_fronteira_efetiva_e_excluem_flags():
    X=pd.DataFrame([[0,0,39,7,0],[0,0,2,0,0],[1,0,39,7,0],[0,1,39,7,0]],
        columns=["risco_seguranca","servico_essencial_interrompido","pessoas_afetadas","dias_aguardando","recorrente"])
    pesos=pesos_fronteira(X)
    assert pesos[0]>pesos[1]>0
    assert pesos[2]==pesos[3]==0


def test_zero_ruido_reproduz_alvo_sem_mutacao():
    df=carregar_dados(); y=df.prioridade.to_numpy()
    novo,indices=gerar_ruido(df,y,0,42,"fronteira")
    assert not len(indices)
    assert np.array_equal(novo,y)
    novo[0]=1-novo[0]
    assert y[0]==politica(df)[0]


def test_execucao_reduzida_salva_resultados_reais_e_mantem_teste_limpo(tmp_path):
    (tmp_path/"dados").mkdir()
    shutil.copy2(ROOT/"dados/chamados_ficticios.csv",tmp_path/"dados/chamados_ficticios.csv")
    original=(tmp_path/"dados/chamados_ficticios.csv").read_bytes()
    r=executar(tmp_path,seeds=[42],taxas=[0,.1])
    assert len(r["execucoes"])==2*2*7
    treino=set(r["protocolo"]["treino_ids"]); teste=set(r["protocolo"]["teste_ids"])
    assert treino.isdisjoint(teste)
    for linha in r["execucoes"]:
        assert set(linha["ids_invertidos"])<=treino
        if linha["modelo"]=="Regras": assert linha["metricas_teste_limpo"]["f2"]==1
        if linha["modelo"]=="ArvoreGridSearch":
            assert linha["max_depth_escolhido"] in [1,2,3,4,5,6,None]
    assert (tmp_path/"relatorios/experimento_ruido.json").is_file()
    assert (tmp_path/"relatorios/figuras/ruido_f2.png").is_file()
    assert original==(tmp_path/"dados/chamados_ficticios.csv").read_bytes()
