"""Monta relatório e roteiro exclusivamente a partir dos resultados executados.

Uso: python scripts/gerar_relatorio_ia.py [--pdf]
Não treina modelos nem chama serviços externos.
"""
from pathlib import Path
from collections import Counter
import argparse
import json
import re
from html import escape
from io import BytesIO

ROOT = Path(__file__).resolve().parents[1]
NOMES = {'Dummy': 'Dummy maioria', 'Regras': 'Política explícita', 'Arvore': 'Árvore atual',
         'Logistica': 'Regressão logística', 'RandomForest': 'Random forest',
         'ArvoreLimitada': 'Árvore limitada', 'ArvoreGridSearch': 'Árvore com GridSearch'}
METRICAS = ['sensibilidade', 'precisao', 'f1', 'f2', 'acuracia']


def numero(x):
    return f'{x:.4f}'.replace('.', ',')


def medida(x):
    return numero(x['media']) + ' ± ' + numero(x['desvio_padrao'])


def tabela(cabecalho, linhas):
    return '\n'.join(['| ' + ' | '.join(cabecalho) + ' |',
                      '| ' + ' | '.join(['---'] * len(cabecalho)) + ' |',
                      *['| ' + ' | '.join(map(str, linha)) + ' |' for linha in linhas]])


def executar(raiz=ROOT, pdf=False):
    raiz = Path(raiz)
    def ler(nome):
        return json.loads((raiz / 'relatorios' / (nome + '.json')).read_text())
    cv, it, fr, ruido, curva, texto = [ler(n) for n in ('comparacao_modelos', 'interpretabilidade',
        'fronteiras', 'experimento_ruido', 'curva_aprendizado', 'classificador_texto')]
    partes = ['# Relatório acadêmico de Inteligência Artificial',
        '**Sistema Inteligente para Priorização de Chamados de Manutenção**',
        '**Engenharia de Computação · Integrante único: Guilherme Costa**',
        '## 1. Problema, hipótese e papel do ML',
        'O protótipo apoia a triagem de manutenção por uma pessoa. A prioridade usa cinco campos confirmados; '
        'o experimento textual sugere equipe a partir da descrição. Toda a base é fictícia e a foto não entra em nenhum dos modelos treinados aqui.',
        'A prioridade foi rotulada por uma política determinística conhecida. Nesse contexto, regras explícitas são '
        'uma solução suficiente e mais direta: os resultados não justificam substituir regras estáveis por ML. '
        'O objetivo acadêmico dos modelos aprendidos é estudar generalização entre famílias, incerteza, erros, '
        'sensibilidade a ruído e limites de aprender a partir de poucos exemplos. Uma aplicação operacional exigiria '
        'rótulos reais independentes, especialistas e avaliação prospectiva.',
        '## 2. Dados, política e separação',
        f"O desenvolvimento contém {cv['protocolo']['desenvolvimento']['registros']} registros em "
        f"{cv['protocolo']['desenvolvimento']['familias']} famílias; os "
        f"{cv['protocolo']['teste_reservado']['registros']} registros de "
        f"{cv['protocolo']['teste_reservado']['familias']} famílias reservadas permanecem separados. "
        'A divisão original é a primeira partição do StratifiedGroupKFold com embaralhamento e semente 42. '
        'O reservado já havia sido consultado no protótipo; seu uso agora é continuidade e exploração, não nova confirmação independente.',
        'X = risco_seguranca, servico_essencial_interrompido, pessoas_afetadas, dias_aguardando e recorrente; '
        'y = prioridade. A política dá classe 1 por risco ou serviço essencial interrompido, ou por pessoas >= 40 '
        'e dias >= 7, ou por recorrência com pessoas >= 10 e dias >= 14. Os demais casos recebem classe 0.',
        'As colunas equipe_rotulo e equipe_justificativa foram acrescentadas por anotação editorial didática de família. '
        'As colunas originais, os rótulos de prioridade e os artefatos do aplicativo foram preservados. '
        'A taxonomia e as justificativas estão em [rotulagem de equipes](../dados/rotulagem_equipes.md).',
        '## 3. Baselines e validação agrupada repetida',
        f"Foram executadas {cv['protocolo']['repeticoes']} repetições com sementes distintas, cada uma com cinco folds "
        'somente no desenvolvimento. Todas as variações de uma família permanecem juntas. '
        'A padronização da regressão logística é ajustada exclusivamente no treino de cada fold. '
        'A árvore usa profundidade máxima 6 e semente 42; os hiperparâmetros dos demais modelos são fixos e estão no JSON. '
        'A comparação não é uma nova seleção aninhada da profundidade escolhida no protótipo.',
        'A tabela mostra média ± desvio-padrão amostral das métricas OOF agregadas por repetição. '
        'Sensibilidade, precisão, F1 e F2 referem-se à classe prioritária; acurácia é global. '
        'F2 dá peso maior à sensibilidade. Divisões por zero recebem zero, documentadas no código.',
        tabela(['Modelo', 'Sensibilidade', 'Precisão', 'F1', 'F2', 'Acurácia'], [
            [NOMES[n], *[medida(v['validacao_cruzada'][m]) for m in METRICAS]] for n, v in cv['modelos'].items()]),
        'Intervalos de confiança percentis de 95%: bootstrap de famílias inteiras, mantendo juntas todas as '
        f"variações e repetições, com {cv['protocolo']['bootstrap']['amostras']} reamostragens. "
        'A estatística reamostrada é a média das métricas OOF por repetição. Não se tratam os folds nem '
        'as repetições sobrepostas como novas observações independentes.',
        tabela(['Modelo', *METRICAS], [[NOMES[n], *[
            '[' + '; '.join(numero(x) for x in v['validacao_cruzada'][m]['ic95_bootstrap_familias']) + ']'
            for m in METRICAS]] for n, v in cv['modelos'].items()]),
        'Os intervalos são condicionais às famílias sintéticas observadas; não incluem toda a incerteza de geração, '
        'rotulagem e mudança de instituição. Um intervalo [1;1] para regras não prova segurança em dados reais.',
        '### Teste reservado para continuidade',
        tabela(['Modelo', 'Sensibilidade', 'Precisão', 'F1', 'F2', 'Acurácia'], [
            [NOMES[n], *[numero(v['teste_reservado'][m]) for m in METRICAS]] for n, v in cv['modelos'].items()]),
        'Fonte: [comparacao_modelos.json](../relatorios/comparacao_modelos.json). '
        'A árvore no reservado é o estimador original; na CV são ajustadas novas árvores com a mesma configuração, em treinos menores.',
        '## 4. Interpretabilidade da árvore preservada',
        f"A árvore possui profundidade {it['profundidade']}, {it['nos']} nós e foi ajustada nos "
        f"{it['amostras_treino']} registros originais de treino. Os cortes recuperam a política neste domínio inteiro.",
        tabela(['Campo', 'Corte aprendido', 'Primeiro inteiro à direita', 'Equivalente'], [
            [l['atributo'], l['limiar_aprendido'], l['primeiro_inteiro_ramo_direito'],
             'Sim' if l['equivalente_em_inteiros'] else 'Não'] for l in it['limiares']]),
        'Os cortes intermediários entre inteiros consecutivos são numericamente diferentes dos limiares escritos, '
        'mas representam a mesma decisão. Em outras amostras pequenas, cortes equivalentes sobre os pontos observados '
        'podem divergir em regiões não cobertas; por isso a análise de fronteiras e OOF é necessária. '
        'Importância por redução de impureza descreve esta árvore, sem interpretação causal e sem medir relevância universal.',
        '![Árvore aprendida](../relatorios/figuras/arvore_publicada.png)',
        '![Importâncias da árvore](../relatorios/figuras/importancias_arvore.png)',
        'Fonte: [interpretabilidade.json](../relatorios/interpretabilidade.json), export_text e limiares_arvore.csv.',
        '## 5. Fronteiras e análise de erros',
        f"A grade contém {fr['grade']['registros']} combinações únicas: os dois blocos de pessoas e de dias "
        'ao redor dos limiares, cruzados com risco, essencial e recorrência binários. '
        'É uma verificação de consistência derivada da própria política, não validação externa.',
        tabela(['Modelo', 'Divergências', 'FN', 'FP', 'FN/positivos'], [
            [NOMES[n], v['divergencias'], v['falsos_negativos'], v['falsos_positivos'],
             numero(v['taxa_falsos_negativos'])] for n, v in fr['modelos'].items()]),
        'As taxas por região, com denominadores e ausência de positivos identificada como nulo, estão em '
        '[falsos_negativos_regioes.csv](../relatorios/falsos_negativos_regioes.csv). '
        'A ausência de divergência da árvore publicada nessa grade não implica que árvores treinadas em outros subconjuntos recuperem todos os cortes.',
        '![Fronteiras da árvore](../relatorios/figuras/fronteiras_arvore.png)',
        '![Fronteiras da regressão logística](../relatorios/figuras/fronteiras_logistica.png)',
        '![Fronteiras da random forest](../relatorios/figuras/fronteiras_randomforest.png)',
        '### Erros OOF mesmo com teste reservado perfeito',
        tabela(['Modelo', 'Ocorrências erradas', 'Falsos negativos'], [[NOMES[n], v['erros_oof'],
                v['falsos_negativos_oof']] for n, v in cv['modelos'].items()]),
        'Ocorrências incluem o mesmo ID em repetições diferentes, portanto não são quantidade de chamados independentes. '
        'A lista integral contém ID, família, seed, fold, campos, classe real e prevista em '
        '[erros_oof_modelos.csv](../relatorios/erros_oof_modelos.csv). Exemplos medidos da árvore:']
    erros = [e for e in cv['erros_oof'] if e['modelo'] == 'Arvore']
    vistos = set(); exemplos = []
    for e in erros:
        if e['id'] not in vistos and len(exemplos) < 8:
            vistos.add(e['id']); exemplos.append([e['id'], e['familia_cenario'], e['prioridade'], e['previsto'], e['tipo_erro']])
    partes += [tabela(['ID', 'Família', 'Real', 'Previsto', 'Erro'], exemplos),
        '## 6. Experimento de ruído de rótulos',
        'A unidade de corrupção é o registro. Invertem-se apenas rótulos do treino, sem modificar X ou o teste limpo. '
        f"Foram usadas {len(ruido['protocolo']['seeds_ruido'])} sementes de ruído, com taxas nominais "
        + ', '.join(str(int(t * 100)) + '%' for t in ruido['protocolo']['taxas_nominais']) + '. '
        'A quantidade real é round(taxa × tamanho do treino), a mesma nos dois modos. '
        'O ruído de fronteira favorece pontos próximos à classe oposta segundo a política e protege casos com risco ou essencial. '
        'É uma hipótese artificial de desacordo, não medição de avaliadores reais.',
        'São comparados os mesmos modelos, uma árvore de profundidade limitada a 3 e uma árvore com GridSearch '
        'em profundidades 1 a 6 ou sem limite, usando quatro folds agrupados de treino ruidoso e F2. '
        'O teste limpo é reutilizado para explorar os efeitos, sem selecionar a árvore do aplicativo.',
        '![Sensibilidade versus ruído](../relatorios/figuras/ruido_sensibilidade.png)',
        '![F2 versus ruído](../relatorios/figuras/ruido_f2.png)',
        'Resumo na maior taxa nominal avaliada; média ± desvio-padrão entre sementes:',
        tabela(['Ruído', 'Modelo', 'F2 teste limpo', 'Sensibilidade teste', 'F2 treino ruidoso'], [
            [r['modo'], NOMES[r['modelo']], medida(r['metricas']['teste_limpo']['f2']),
             medida(r['metricas']['teste_limpo']['sensibilidade']), medida(r['metricas']['treino_ruidoso']['f2'])]
            for r in ruido['resumo'] if r['taxa_nominal'] == max(ruido['protocolo']['taxas_nominais'])]),
        'A diferença entre desempenho no treino ruidoso e no teste limpo e a frequência de profundidades selecionadas '
        'permitem discutir sobreajuste. Não se deve concluir que limitar a profundidade ou usar regressão logística '
        'sempre melhora a robustez; o resultado depende de como o erro de rótulo foi gerado. A regra explícita '
        'não aprende rótulos corrompidos e permanece uma referência favorecida pelo desenho do experimento.']
    for modo in ('uniforme', 'fronteira'):
        item = next(r for r in ruido['resumo'] if r['modo'] == modo and r['modelo'] == 'ArvoreGridSearch'
                    and r['taxa_nominal'] == max(ruido['protocolo']['taxas_nominais']))
        partes.append(f"GridSearch, {modo}: frequências de profundidade máxima escolhida = "
                      + json.dumps(item['frequencia_max_depth_escolhido'], ensure_ascii=False) + '. '
                      'A escolha usou apenas o treino ruidoso; não foi aplicada ao modelo publicado.')
    partes += ['Fonte: [experimento_ruido.json](../relatorios/experimento_ruido.json), com todas as sementes e posições invertidas.',
        '## 7. Curva de aprendizado',
        'Subconjuntos aninhados de famílias do treino externo são avaliados em famílias externas separadas, '
        'sem usar os exemplos reservados. O menor prefixo garante as duas classes usando apenas o treino externo.',
        tabela(['Modelo', 'Famílias', 'F2 treino', 'F2 validação', 'Sensibilidade validação'], [
            [NOMES[r['modelo']], r['familias_treino'], medida(r['treino']['f2']), medida(r['validacao']['f2']),
             medida(r['validacao']['sensibilidade'])] for r in curva['resumos']]),
        '![Curva de aprendizado](../relatorios/figuras/curva_aprendizado.png)',
        'A melhora com mais famílias mede cobertura de cenários sintéticos. Não comprova que esta base seja suficiente '
        'para uso real: cada família repete uma descrição e os rótulos de prioridade já seguem uma regra conhecida. '
        'A regressão logística também tem limitação de representação de interações; aumentar a amostra não elimina automaticamente esse viés.',
        'Fonte: [curva_aprendizado.json](../relatorios/curva_aprendizado.json).',
        '## 8. Classificador textual de equipe',
        'Pipeline treinado: limpeza do sufixo de variação, TF-IDF de palavras/unigramas e bigramas em união com '
        'n-gramas de caracteres de 3 a 5, seguido de regressão logística. O vocabulário e os pesos são ajustados '
        'somente no treino de cada fold. A prioridade, números de pessoas/dias gerados, foto, ID e família não entram no classificador.',
        tabela(['Método', 'Acurácia OOF', 'F1 macro OOF'], [[n, medida(v['acuracia']), medida(v['f1_macro'])]
                for n, v in texto['modelos'].items()]),
        'Critério anterior à integração: superar estritamente a regra local nas duas médias OOF. '
        + texto['gate']['decisao'],
        'O modelo textual ficou abaixo da regra local: não substituiu o comportamento do Flask. '
        'Seu artefato e os testes são entregues como experimento. A baixa generalização entre famílias '
        'é um resultado relevante, favorecido por pouca diversidade textual e poucas famílias por especialidade. '
        'Não foram geradas paráfrases extras nem misturadas variações no reservado.',
        'As matrizes de confusão somam predições OOF repetidas, não novos registros independentes. '
        'A lista completa de erros e a matriz estão em [classificador_texto.json](../relatorios/classificador_texto.json) '
        'e classificador_texto_oof.csv. O teste reservado é mostrado separadamente e não decidiu a integração.',
        tabela(['Método', 'Acurácia reservada', 'F1 macro reservado'], [
            [n, numero(v['acuracia']), numero(v['f1_macro'])] for n, v in texto['teste_reservado'].items()]),
        'O reservado foi estratificado por prioridade, não por equipe, e só contém Hidráulica e Triagem geral. '
        'O F1 macro usa as quatro classes fixas, atribuindo zero às classes ausentes. Portanto mesmo a regra '
        'que acerta todos os registros reservados não obtém F1 macro igual a um; não se deve comparar esse '
        'número diretamente à acurácia nem usá-lo para escolher o classificador textual.',
        '![Matrizes de confusão de equipes](../relatorios/figuras/matriz_equipes.png)',
        '## 9. Ameaças à validade',
        '- **Circularidade:** o baseline de regras conhece o gerador dos rótulos. A grade deriva da mesma política. '
        'Consistência é diferente de validação externa.\n'
        '- **Amostra pequena e dependente:** variações de uma família não são observações independentes. '
        'Separação por família, IC em blocos e OOF reduzem vazamento, sem criar diversidade real.\n'
        '- **Incerteza parcial:** bootstrap condicional e desvio-padrão entre repetições não incluem mudança de domínio '
        'ou todas as decisões anteriores de projeto. O reservado já foi visto e reutilizado exploratoriamente no ruído.\n'
        '- **Ruído hipotético:** inversões artificiais e pesos de fronteira não reproduzem todos os motivos de discordância humana. '
        'Diferenças de robustez não justificam implantação.\n'
        '- **Rótulos de equipe didáticos:** não houve validação institucional independente nem anotação por múltiplos especialistas. '
        'Famílias de teste com palavras novas expõem a escassez do treino textual.\n'
        '- **Escopo:** todos os dados são fictícios. Nenhuma chamada real à OpenAI foi feita. '
        'Uma instituição parceira precisará definir critérios, anonimização, dupla rotulagem e avaliação prospectiva por grupos e períodos.',
        '## 10. Execução e preservação do protótipo',
        'O notebook incorpora código, dados e os artefatos necessários em um pacote interno e executa tudo em '
        'diretório temporário, sem upload manual e sem escrever sobre o modelo do aplicativo. '
        'As saídas foram verificadas localmente com nbclient; compatibilidade com Colab não equivale a execução no serviço Google. '
        'O relatório de execução fica em relatorios/execucao_notebook.json.',
        'Os comandos de reprodução estão no README. O arquivo modelo/arvore.json, o estimador original e a inferência '
        'JavaScript são preservados. A engenharia de fotos, SQLite, APIs e Pages está documentada em '
        '[Extras de engenharia](EXTRAS_ENGENHARIA.md). O classificador textual é apenas Flask/Python experimental; '
        'não é necessário para a demonstração estática nem muda a prioridade.']
    pasta = raiz / 'docs_academicos'; pasta.mkdir(exist_ok=True)
    destino = pasta / 'RELATORIO_ACADEMICO.md'
    destino.write_text('\n\n'.join(partes) + '\n', encoding='utf-8')
    roteiro = ['# Roteiro de apresentação de Inteligência Artificial',
        '**Guilherme Costa · Engenharia de Computação**',
        '1. Apresentar o problema e declarar que todos os dados são fictícios.',
        '2. Explicar a política e o baseline forte: se as regras geram os rótulos, ML não é necessário para executá-las.',
        '3. Mostrar a árvore, os cortes equivalentes em inteiros e a importância sem interpretação causal.',
        '4. Comparar teste reservado, OOF repetido e IC por família; mostrar um erro OOF apesar do teste perfeito.',
        '5. Mostrar a grade de fronteiras como teste de consistência, sem chamar isso de validação externa.',
        '6. Exibir gráficos de ruído e a seleção de profundidade, comparando treino ruidoso e teste limpo.',
        '7. Mostrar a curva por quantidade de famílias e discutir cobertura e viés.',
        '8. Apresentar TF-IDF de palavras/caracteres e a comparação com palavras-chave. Explicar por que o experimento não foi integrado.',
        '9. Demonstrar que a prioridade no aplicativo permanece idêntica e listar as ameaças à validade.',
        '10. Consultar as tabelas do relatório e os JSON para todos os números citados. '
        'O notebook permite reproduzir os experimentos; a documentação de engenharia preserva o roteiro do protótipo.']
    (pasta / 'ROTEIRO_DEMONSTRACAO.md').write_text('\n\n'.join(roteiro) + '\n', encoding='utf-8')
    if pdf:
        gerar_pdf(destino)
    return destino


def gerar_pdf(fonte):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas
    from pypdf import PdfReader, PdfWriter
    pdfmetrics.registerFont(TTFont('Fonte', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('Fonte-Bold', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
    pdfmetrics.registerFontFamily('Fonte', normal='Fonte', bold='Fonte-Bold')
    estilos = getSampleStyleSheet()
    base = ParagraphStyle('BaseIA', fontName='Fonte', fontSize=9, leading=13, spaceAfter=7)
    titulo = ParagraphStyle('TituloIA', parent=base, fontName='Fonte-Bold', fontSize=18, leading=23, keepWithNext=True)
    secao = ParagraphStyle('SecaoIA', parent=base, fontName='Fonte-Bold', fontSize=12, leading=16, spaceBefore=8, keepWithNext=True)
    celula = ParagraphStyle('CelulaIA', parent=base, fontSize=7, leading=10, spaceAfter=0)
    def inline(s):
        s = escape(s)
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        s = re.sub(r'`([^`]+)`', r'\1', s)
        s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
        return s
    linhas = fonte.read_text().splitlines(); itens = []; i = 0; largura = A4[0] - 84
    while i < len(linhas):
        linha = linhas[i]; i += 1
        if not linha.strip(): continue
        figura = re.fullmatch(r'!\[([^]]*)\]\(([^)]+)\)', linha)
        if figura:
            imagem = Image(str((fonte.parent / figura[2]).resolve()))
            escala = min(largura / imagem.imageWidth, 330 / imagem.imageHeight)
            imagem.drawWidth = imagem.imageWidth * escala; imagem.drawHeight = imagem.imageHeight * escala
            itens.append(KeepTogether([imagem, Paragraph(inline(figura[1]), celula), Spacer(1, 10)])); continue
        if linha.startswith('|'):
            bloco = [linha]
            while i < len(linhas) and linhas[i].startswith('|'):
                bloco.append(linhas[i]); i += 1
            dados = []
            for l in bloco:
                cols = [c.strip() for c in l.strip('|').split('|')]
                if all(re.fullmatch(r':?-+:?', c) for c in cols): continue
                dados.append([Paragraph(inline(c), celula) for c in cols])
            t = Table(dados, colWidths=[largura / len(dados[0])] * len(dados[0]), repeatRows=1)
            t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e1efe9')),
                ('GRID',(0,0),(-1,-1),.3,colors.HexColor('#bdd1c8')),('VALIGN',(0,0),(-1,-1),'TOP'),
                ('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
            itens += [t, Spacer(1, 8)]; continue
        estilo = titulo if linha.startswith('# ') else secao if linha.startswith('##') else base
        itens.append(Paragraph(inline(re.sub(r'^#+\s*', '', linha)), estilo))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=42, rightMargin=42, topMargin=40, bottomMargin=40,
                            title='Relatório de Inteligência Artificial', author='Guilherme Costa')
    def rodape(canvas, documento):
        canvas.setFont('Fonte', 7); canvas.drawString(42, 24, 'Guilherme Costa · Dados fictícios · Inteligência Artificial')
        canvas.drawRightString(A4[0] - 42, 24, str(documento.page))
    doc.build(itens, onFirstPage=rodape, onLaterPages=rodape,
              canvasmaker=lambda *a, **k: Canvas(*a, **{**k, 'invariant': 1}))
    leitor = PdfReader(BytesIO(buffer.getvalue())); escritor = PdfWriter(); escritor.clone_document_from_reader(leitor)
    for k in ('/CreationDate', '/ModDate'):
        if escritor.metadata and k in escritor.metadata: escritor._info.get_object().pop(k, None)
    with fonte.with_suffix('.pdf').open('wb') as arquivo: escritor.write(arquivo)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--pdf', action='store_true')
    print(executar(pdf=p.parse_args().pdf))
