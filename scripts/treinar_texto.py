"""Experimento textual por famílias, com seleção independente do teste reservado."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold

from scripts.ml_comum import carregar_dados, divisao_original, hash_dados_numericos, salvar_json, versoes
from texto_equipe import EQUIPES_TEXTO, ROTULOS_POR_FAMILIA, anotar_equipes, criar_pipeline, limpar_descricao


def prever_regra(textos):
    from multimodal import alternativa_local
    return np.array([alternativa_local(limpar_descricao(t))['equipe_sugerida'] for t in textos])


def medir(y, pred):
    return {'acuracia': float(accuracy_score(y, pred)),
            'f1_macro': float(f1_score(y, pred, labels=EQUIPES_TEXTO, average='macro', zero_division=0)),
            'matriz_confusao': confusion_matrix(y, pred, labels=EQUIPES_TEXTO).tolist()}


def superou_regra(modelos):
    """Critério pré-fixado: melhoria estrita em ambas as métricas de desenvolvimento."""
    return all(modelos['TFIDF_Logistica'][m]['media'] > modelos['Regra_local'][m]['media'] for m in ['acuracia','f1_macro'])


def avaliar_texto(df, repeticoes=10):
    desenvolvimento, reservado = divisao_original(df)
    dev = df.iloc[desenvolvimento].reset_index(drop=True)
    registros = []
    por_repeticao = []
    for repeticao in range(repeticoes):
        seed = 42 + repeticao
        cv = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        predicoes = {nome: np.empty(len(dev), dtype=object) for nome in ['TFIDF_Logistica', 'Regra_local']}
        for fold, (treino, validacao) in enumerate(cv.split(dev.descricao, dev.equipe_rotulo, dev.familia_cenario)):
            familias_treino = set(dev.iloc[treino].familia_cenario)
            assert not familias_treino & set(dev.iloc[validacao].familia_cenario)
            pipeline = criar_pipeline(seed=42)
            pipeline.fit(dev.iloc[treino].descricao, dev.iloc[treino].equipe_rotulo)
            predicoes['TFIDF_Logistica'][validacao] = pipeline.predict(dev.iloc[validacao].descricao)
            predicoes['Regra_local'][validacao] = prever_regra(dev.iloc[validacao].descricao)
            for pos in validacao:
                registros.append({'repeticao': repeticao, 'seed': seed, 'fold': fold,
                    'id': dev.iloc[pos].id, 'familia_cenario': dev.iloc[pos].familia_cenario,
                    'descricao': limpar_descricao(dev.iloc[pos].descricao), 'real': dev.iloc[pos].equipe_rotulo,
                    **{nome: predicoes[nome][pos] for nome in predicoes}})
        por_repeticao.append({'seed': seed, 'modelos': {nome: medir(dev.equipe_rotulo, pred) for nome, pred in predicoes.items()}})
    modelos = {}
    oof = pd.DataFrame(registros)
    for nome in predicoes:
        scores = {m: np.array([r['modelos'][nome][m] for r in por_repeticao]) for m in ['acuracia', 'f1_macro']}
        modelos[nome] = {m: {'media': float(v.mean()), 'desvio_padrao': float(v.std(ddof=1)) if len(v)>1 else 0.0} for m, v in scores.items()}
        modelos[nome]['matriz_confusao_oof_somada'] = confusion_matrix(oof.real, oof[nome], labels=EQUIPES_TEXTO).tolist()
        modelos[nome]['erros_oof'] = oof.loc[oof.real != oof[nome], ['repeticao','seed','fold','id','familia_cenario','descricao','real',nome]].rename(columns={nome:'previsto'}).to_dict(orient='records')
    melhor = superou_regra(modelos)
    # O gate é fechado antes de qualquer avaliação do conjunto reservado.
    pipeline = criar_pipeline(seed=42).fit(dev.descricao, dev.equipe_rotulo)
    teste = df.iloc[reservado]
    resultado = {'origem': 'Dados fictícios; anotação editorial didática de equipe por família.',
        'protocolo': {'desenvolvimento_registros': len(dev), 'desenvolvimento_familias': int(dev.familia_cenario.nunique()),
                     'teste_reservado_registros': len(teste), 'teste_reservado_familias': int(teste.familia_cenario.nunique()),
                     'repeticoes': repeticoes, 'folds': 5, 'seeds': list(range(42,42+repeticoes)),
                     'ids_desenvolvimento': dev.id.tolist(), 'ids_teste_reservado': teste.id.tolist(),
                     'agrupamento': 'familia_cenario; TF-IDF ajustado somente no treino de cada fold',
                     'dispersao': 'desvio-padrão amostral entre métricas OOF agregadas de cada repetição; repetições compartilham dados',
                     'entrada': 'Somente descrição limpa; sufixo de variação e contagens geradas removido',
                     'aumento_sintetico': False, 'teste_reservado_usado_na_selecao': False,
                     'f1_macro': 'Média das quatro classes fixas, com zero_division=0; classe ausente tem F1 zero.'},
        'ordem_classes': EQUIPES_TEXTO, 'distribuicao_familias': df.drop_duplicates('familia_cenario').equipe_rotulo.value_counts().to_dict(),
        'modelos': modelos, 'por_repeticao': por_repeticao,
        'gate': {'criterio': 'Superar estritamente a regra local em acurácia média e F1 macro médio de desenvolvimento OOF.',
                 'superou_regra': melhor, 'habilitado_local': melhor,
                 'decisao': 'Modelo textual elegível para alternativa local.' if melhor else 'Regra local preservada; modelo textual permanece experimental.'},
        'suporte_teste_reservado': {equipe:int(teste.equipe_rotulo.eq(equipe).sum()) for equipe in EQUIPES_TEXTO},
        'teste_reservado': {'TFIDF_Logistica': medir(teste.equipe_rotulo, pipeline.predict(teste.descricao)),
                           'Regra_local': medir(teste.equipe_rotulo, prever_regra(teste.descricao))},
        'hash_dados_numericos': hash_dados_numericos(df), 'versoes': versoes(),
        'limitacoes': ['Anotação de equipe didática, sem validação por instituição ou especialistas independentes.',
                       'Descrições de uma família compartilham o enunciado; separação por família é necessária.',
                       'Poucas famílias por equipe tornam a avaliação instável; variações sintéticas não substituem novos casos.',
                       'Matriz OOF soma repetições e não representa observações independentes.',
                       'O teste reservado original foi estratificado por prioridade, não por equipe; pode não conter todas as equipes. F1 macro mantém as quatro classes e atribui zero às ausentes.',
                       'Não há análise de foto neste modelo; equipe não determina prioridade.']}
    return resultado, pipeline, oof


def plotar_matrizes(resultado, destino):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    destino=Path(destino); destino.parent.mkdir(parents=True,exist_ok=True)
    figura,eixos=plt.subplots(1,2,figsize=(12,5),layout='constrained')
    for eixo,(nome,medidas) in zip(eixos,resultado['modelos'].items()):
        matriz=np.array(medidas['matriz_confusao_oof_somada'])
        imagem=eixo.imshow(matriz,cmap='Blues',vmin=0)
        for i in range(4):
            for j in range(4):
                eixo.text(j,i,str(matriz[i,j]),ha='center',va='center',color='white' if matriz[i,j]>matriz.max()/2 else 'black')
        eixo.set_xticks(range(4),EQUIPES_TEXTO,rotation=35,ha='right')
        eixo.set_yticks(range(4),EQUIPES_TEXTO)
        eixo.set(xlabel='Equipe prevista',ylabel='Equipe anotada',title=nome)
        figura.colorbar(imagem,ax=eixo,shrink=.8)
    figura.suptitle('Equipes: matrizes OOF somadas entre repetições\nContagens repetidas; não são observações independentes',fontsize=11)
    figura.savefig(destino,dpi=160);plt.close(figura)


def executar(raiz=ROOT, repeticoes=10):
    raiz=Path(raiz)
    original=carregar_dados(raiz)
    df=anotar_equipes(original)
    resultado, pipeline, oof=avaliar_texto(df,repeticoes=repeticoes)
    (raiz/'dados').mkdir(exist_ok=True); (raiz/'modelo').mkdir(exist_ok=True); (raiz/'relatorios').mkdir(exist_ok=True)
    df.to_csv(raiz/'dados/chamados_ficticios.csv',index=False,lineterminator='\n')
    anotacoes=pd.DataFrame([{'familia_cenario':f,'equipe_rotulo':r[0],'justificativa':r[1]} for f,r in ROTULOS_POR_FAMILIA.items()])
    anotacoes.to_csv(raiz/'dados/rotulagem_equipes.csv',index=False,lineterminator='\n')
    oof.to_csv(raiz/'relatorios/classificador_texto_oof.csv',index=False,lineterminator='\n')
    resultado['figura_matrizes']='relatorios/figuras/matriz_equipes.png'
    plotar_matrizes(resultado,raiz/resultado['figura_matrizes'])
    salvar_json(raiz/'relatorios/classificador_texto.json',resultado)
    joblib.dump(pipeline,raiz/'modelo/equipe_texto.joblib')
    metadata={'habilitado_local':resultado['gate']['habilitado_local'], 'criterio':resultado['gate']['criterio'],
              'motivo':resultado['gate']['decisao'], 'arquivo_metricas':'relatorios/classificador_texto.json',
              'classes':EQUIPES_TEXTO,'entrada':'Descrição somente; nenhuma foto ou campo de prioridade',
              'familias_treino': sorted(df.iloc[divisao_original(df)[0]].familia_cenario.unique().tolist()),
              'ids_treino':df.iloc[divisao_original(df)[0]].id.tolist(),
              'pipeline': 'Limpeza + FeatureUnion(TF-IDF palavras 1–2, char_wb 3–5) + LogisticRegression(C=1,max_iter=2000,random_state=42)',
              'versoes':versoes()}
    salvar_json(raiz/'modelo/equipe_texto_metadata.json',metadata)
    tabela=pd.DataFrame([{'modelo':nome,**{f'{m}_media':v[m]['media'] for m in ['acuracia','f1_macro']},
                        **{f'{m}_desvio_padrao':v[m]['desvio_padrao'] for m in ['acuracia','f1_macro']}} for nome,v in resultado['modelos'].items()])
    tabela.to_csv(raiz/'relatorios/classificador_texto.csv',index=False,lineterminator='\n')
    texto=['# Anotação didática de equipes','',
           'A anotação foi definida por família para este experimento. Não foi produzida por API ou pela regra de palavras-chave, e não constitui validação técnica real. As quatro variações de cada família recebem a mesma equipe. Os cinco campos e os rótulos de prioridade permanecem intactos.','',
           'TI inclui informática e suporte audiovisual; Elétrica inclui iluminação, tomadas, ventilação elétrica e energia; Hidráulica inclui água e saneamento. Ferragens, estruturas, refrigeração, elevador e gás permanecem em Triagem geral, pois a taxonomia não representa todas as especialidades.','',
           'A modelagem usa somente a descrição, removendo o sufixo gerado com números de pessoas, dias e recorrência. O conjunto reservado não orienta parâmetros nem a decisão de integrar. A comparação usa as mesmas partições agrupadas para o modelo e a regra.','',
           '| Família | Equipe anotada | Justificativa |','|---|---|---|']
    texto += [f'| {f} | {rotulo} | {motivo} |' for f,(rotulo,motivo) in ROTULOS_POR_FAMILIA.items()]
    (raiz/'dados/rotulagem_equipes.md').write_text('\n'.join(texto)+'\n',encoding='utf-8')
    print(tabela.to_string(index=False));print(resultado['gate']['decisao'])
    return resultado


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeticoes',type=int,default=10)
    args=parser.parse_args()
    if args.repeticoes < 1: parser.error('Use pelo menos uma repetição; a execução completa utiliza dez.')
    executar(repeticoes=args.repeticoes)
