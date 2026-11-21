# Sistema Inteligente para Priorização de Chamados de Manutenção

**Engenharia de Computação · Guilherme Costa · Dados inteiramente fictícios**

**Sistema de atendimento.** O Flask classifica novos chamados em **Prioritário**, **Intermediário** ou **Não prioritário**, com análise semântica opcional, regras críticas e justificativa. A fila SQLite ordena pendências por prioridade e horário, mantém o histórico e registra alterações autorizadas. Consulte [instalação, migração, credenciais e validação](docs_academicos/TRIAGEM_E_FILA.md).

## Estudo acadêmico da árvore binária

O protótipo sugere **Normal ou Prioritário** usando uma árvore de decisão sobre cinco campos confirmados por uma pessoa. Esta evolução estuda baselines, generalização por família, incerteza, fronteiras, ruído de rótulos, tamanho do treino e classificação de equipes por texto. A árvore publicada e a inferência no navegador permanecem preservadas.

**Resultado central:** com rótulos gerados por uma política conhecida, executar a política é suficiente. ML é aqui um experimento acadêmico, sem demonstração de vantagem operacional ou validação em instituições reais.

| Modelo | F2 OOF: média ± DP | IC95% por família |
| --- | --- | --- |
| Dummy maioria | 0,5273 ± 0,0000 | [0,4117; 0,6191] |
| Política explícita | 1,0000 ± 0,0000 | [1,0000; 1,0000] |
| Árvore | 0,9776 ± 0,0194 | [0,9551; 0,9918] |
| Regressão logística | 0,7433 ± 0,0077 | [0,5126; 0,8922] |
| Random forest | 0,9939 ± 0,0029 | [0,9836; 1,0000] |

As médias usam dez repetições de CV agrupada apenas no desenvolvimento; IC por bootstrap de famílias. O teste reservado é separado e já havia sido consultado. Fonte de todos os números: [comparação executada](relatorios/comparacao_modelos.json). O classificador textual não superou palavras-chave e ficou experimental. **Incerteza condicional em dados sintéticos não mede segurança real.**

## Como rodar

Use Python 3.12. Na raiz do projeto:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python app.py
```

No Windows, ative com `.venv\Scripts\activate`. Abra http://127.0.0.1:5000. Para executar apenas o aplicativo, `requirements.txt` basta. Chave de IA é opcional; nenhum experimento faz chamadas à OpenAI. Para a paridade, instale também Node.js 18 ou superior.

## Reproduzir experimentos

```bash
python scripts/avaliar_modelos.py
python scripts/interpretar_arvore.py
python scripts/analisar_fronteiras.py
python scripts/experimento_ruido.py
python scripts/curva_aprendizado.py
python scripts/treinar_texto.py
python scripts/gerar_relatorio_ia.py --pdf
python -m pytest -q
```

A avaliação faz dez repetições de cinco folds, com sementes distintas. Ruído usa vinte sementes e cinco taxas, somente no treino, com teste limpo. A curva usa subconjuntos de famílias de treino e validação externa separada. Os parâmetros, IDs, grupos e métricas de cada execução estão nos JSON; os scripts rodam localmente e não regravam a árvore do aplicativo.

O [notebook executado](Projeto_Chamados_Manutencao.ipynb) incorpora fontes e dados, regenera os experimentos em uma pasta temporária e funciona sem upload manual. A execução foi verificada localmente com nbclient. Para reconstruir e executar o notebook:

```bash
python scripts/montar_notebook.py --executar
```

Confira a interface do gerador com `python scripts/montar_notebook.py --help`. O notebook permanece compatível com o Colab; não se afirma execução no serviço Google.

## Resultados e análise

- [Comparação completa: sensibilidade, precisão, F1, F2, acurácia e IC](relatorios/comparacao_modelos.md).
- [Interpretabilidade, erros OOF, ruído, curva, texto e ameaças à validade](docs_academicos/RELATORIO_ACADEMICO.md).
- [Relatório em PDF](docs_academicos/RELATORIO_ACADEMICO.pdf) e [roteiro de apresentação](docs_academicos/ROTEIRO_DEMONSTRACAO.md).
- [Ruído: resultados por semente e profundidade escolhida](relatorios/experimento_ruido.json).
- [Classificador textual e decisão de integração](relatorios/classificador_texto.json).
- [Anotação editorial de equipes](dados/rotulagem_equipes.md).
- [Verificação final: 138 testes e artefatos preservados](relatorios/verificacao_ia.json).

O reservado original foi separado por prioridade e contém somente duas equipes. O F1 macro de equipe usa quatro classes fixas, inclusive ausentes; esse conjunto não seleciona o modelo textual. Não houve aumento sintético textual nem validação real. Uma instituição parceira precisará coletar dados diversos, anonimizar, definir rotulagem independente e avaliar por grupos e períodos.

## Extras de engenharia e entrega

O [guia preservado de engenharia](docs_academicos/EXTRAS_ENGENHARIA.md) reúne todos os detalhes e links de fotos, SQLite, API, Flask, rede local e GitHub Pages. O [roteiro de anexação](docs_academicos/ENTREGA_CLASSROOM.md) organiza os arquivos.

[Baixar a entrega de IA](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao/releases/tag/v3-ia). A [lista completa de arquivos criados e alterados](relatorios/arquivos_ia.json) identifica as mudanças por etapa.

No Flask, **Salvar chamado** grava em SQLite e **Analisar chamado** permite consultar a decisão antes de salvar. O modelo textual de equipe permanece um experimento de Python. A interface operacional usa a triagem híbrida descrita no guia de triagem e fila.

O GitHub Pages permanece uma demonstração estática com exemplos fictícios fixos; não salva cadastros nem executa o classificador textual. Banco, uploads e `.env` ficam fora do Git.

Para empacotar somente o commit atual, sem credenciais, banco, uploads ou pacotes anteriores:

```bash
python scripts/empacotar_entrega.py --saida ../Entrega_IA.zip
```
