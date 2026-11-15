# Sistema Inteligente para Priorização de Chamados de Manutenção

Projeto acadêmico de Engenharia de Computação. **Integrante único: Guilherme Costa.** Entrega prevista: **20/11/2026**.

Protótipo para escolas, ONGs e pequenas instituições: informa cinco características de um chamado e sugere **0 = normal** ou **1 = prioritário**. O responsável revisa a sugestão e decide a ordem do atendimento. A classificação é feita por uma árvore de decisão treinada com scikit-learn.

**Todos os 120 chamados são fictícios.** O sistema não foi validado em uma instituição real, e os resultados apresentados não comprovam segurança ou eficácia em uso operacional. Em situações de risco, a instituição deve aplicar seus procedimentos de emergência e avaliação técnica.

## Executar no computador

Ambiente medido: Python 3.12, pandas 2.2.3, scikit-learn 1.8.0 e Flask 3.1.2. Os comandos abaixo usam um terminal Linux/macOS na raiz do projeto.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python app.py
```

Abra **http://127.0.0.1:5000**. Para outra porta: `PORT=5055 python app.py`. O Flask serve a interface e a API; o JavaScript chama `POST /api/prever` para cada previsão. Para apenas executar o aplicativo e retreinar, `requirements.txt` basta; `requirements-dev.txt` inclui as ferramentas de teste e execução de notebooks.

## Usar o protótipo

1. Preencha a descrição opcional ou carregue um dos exemplos fictícios.
2. Informe risco à segurança, serviço essencial interrompido, pessoas afetadas, dias aguardando e recorrência.
3. Selecione **Analisar chamado** e leia a classe e o resumo.
4. O responsável deve confirmar os dados e definir a ordem do atendimento.

Campos binários aceitam somente `0` ou `1`. Pessoas e dias são inteiros não negativos; campos em branco são desconhecidos e impedem a previsão. A descrição é documental e não entra diretamente no classificador.

## Dados e política de rotulagem

A base reproduzível reúne **120 registros em 30 famílias**, com quatro variações de cada cenário. Contém problemas de baixo impacto, alto impacto e fronteiras dos limiares. ID, descrição, família, origem e justificativa documentam os exemplos; somente os cinco campos numéricos são entradas do modelo.

| Campo de entrada | Significado |
| --- | --- |
| `risco_seguranca` | 0 = sem risco identificado; 1 = risco identificado |
| `servico_essencial_interrompido` | 0 = não; 1 = sim |
| `pessoas_afetadas` | Quantidade inteira não negativa |
| `dias_aguardando` | Quantidade inteira não negativa |
| `recorrente` | 0 = não; 1 = sim |

O alvo é `prioridade`. A política didática foi definida antes do treinamento: classe **1** quando ocorrer pelo menos uma destas condições:

- risco à segurança;
- interrupção de serviço essencial;
- pelo menos 40 pessoas afetadas e 7 dias aguardando;
- recorrência, pelo menos 10 pessoas afetadas e 14 dias aguardando.

Nos demais casos, o rótulo é **0**. Segurança independe da circulação: fiação exposta continua prioritária mesmo afetando poucas pessoas. Água, energia, saneamento, alimentação e acesso indispensável são exemplos de serviços essenciais; equipamento auxiliar com alternativa não é automaticamente essencial. Os limiares de pessoas e espera são escolhas pedagógicas, e precisam ser pactuados com uma instituição antes de uso real. Cada registro contém `justificativa_rotulo`.

## Treinamento e avaliação

`pandas` valida tipos, ausência de valores nulos, IDs únicos, classes e consistência com a política. X contém os cinco campos na ordem documentada no JSON; y é `prioridade`. Descrições, IDs e famílias não são atributos de classificação.

A primeira partição fixa de `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` reserva 24 registros para teste e 96 para treino. Nenhuma família ocorre nos dois conjuntos. A estratificação por grupos aproxima as proporções sem separar variações de um mesmo cenário.

| Conjunto | Registros | Famílias | Normal | Prioritário |
| --- | ---: | ---: | ---: | ---: |
| Base | 120 | 30 | 57 | 63 |
| Treino | 96 | 24 | 47 | 49 |
| Teste reservado | 24 | 6 | 10 | 14 |

A profundidade é escolhida exclusivamente no treino por `GridSearchCV` com quatro partições agrupadas. Foram comparadas profundidades 1 a 6 e sem limite, usando F2 da classe prioritária para dar mais peso à sensibilidade. O desempate favorece o primeiro candidato, menos profundo. Foi escolhida profundidade máxima **6**, e a árvore aprendida tem profundidade **6**. O teste reservado não orienta o ajuste. O comparador é `DummyClassifier(strategy="most_frequent")`, ajustado no treino, cuja classe mais frequente é 1.

Resultados medidos nos **24 registros de teste fictícios**:

| Classificador | Sensibilidade da classe 1 | Precisão da classe 1 | Acurácia |
| --- | ---: | ---: | ---: |
| Árvore | 100,00% | 100,00% | 100,00% |
| Maioria do treino | 100,00% | 58,33% | 58,33% |

Matrizes de confusão, com **linhas = classe real**, **colunas = classe prevista**, ordem `[0, 1]`:

```text
Árvore                   Maioria
             Prev. 0  1               Prev. 0  1
Real 0             10 0  Real 0              0 10
Real 1              0 14 Real 1              0 14
```

A árvore teve 10 verdadeiros negativos, 14 verdadeiros positivos e nenhum erro no teste reservado. **Não houve falsos negativos nesse conjunto**, portanto não há exemplos observados para listar. O classificador de maioria prevê todos como prioritários: sua sensibilidade é alta, mas ele gera dez falsos positivos. As métricas completas, resultados de validação cruzada e versões estão em [relatorios/metricas.json](relatorios/metricas.json); as previsões individuais estão em [relatorios/predicoes_teste.csv](relatorios/predicoes_teste.csv).

O resultado perfeito é compatível com uma amostra pequena cujos rótulos derivam de regras explícitas. A árvore aprende uma aproximação dessa política; não descobre, por si só, riscos reais. Separar famílias reduz vazamento entre variações, mas atributos semelhantes ainda podem existir em famílias diferentes. Ausência de falsos negativos aqui não garante ausência de falhas em novos contextos.

## Notebook e retreinamento

[Projeto_Chamados_Manutencao.ipynb](Projeto_Chamados_Manutencao.ipynb) incorpora a geração da base e todo o processo de validação, divisão, ajuste, avaliação e exportação. Ele não depende de upload de um CSV externo e permanece compatível com o Google Colab. É possível abri-lo em `https://colab.research.google.com/`, escolher **Arquivo → Fazer upload de notebook** e depois **Ambiente de execução → Executar tudo**.

O notebook entregue é executado localmente com `nbclient` no ambiente Codex Cloud; não se deve interpretar esse teste como execução autenticada no Colab. A automação da sessão autenticada do navegador não estava disponível nesta tarefa.

Para reproduzir os artefatos na raiz do projeto:

```bash
python scripts/treinar.py
```

O comando gera o CSV, a divisão treino/teste, as métricas e os artefatos do modelo. Para executar novamente o notebook e conservar suas saídas:

```bash
python -c "from pathlib import Path; import nbformat; from nbclient import NotebookClient; p=Path('Projeto_Chamados_Manutencao.ipynb'); n=nbformat.read(p,as_version=4); NotebookClient(n,timeout=600,kernel_name='python3',resources={'metadata':{'path':str(Path.cwd())}}).execute(); nbformat.write(n,p)"
```

Após qualquer retreinamento, prepare novamente os arquivos estáticos e repita os testes de paridade antes de publicar.

## Árvore compartilhada e API

`modelo/arvore.json` contém ordem dos atributos, classes, nós, índices de atributos, limiares, filhos, contagens e classe de cada nó, além de metadados de reprodução. O Flask e o navegador percorrem essa mesma árvore. O arquivo `modelo/arvore.joblib` permite comparar o estimador original do scikit-learn nos testes; o servidor não carrega objetos pickle fornecidos por visitantes.

Exemplo de requisição:

```bash
curl -X POST http://127.0.0.1:5000/api/prever \
  -H 'Content-Type: application/json' \
  -d '{"risco_seguranca":1,"servico_essencial_interrompido":0,"pessoas_afetadas":1,"dias_aguardando":0,"recorrente":0,"descricao":"Fiação exposta em local de pouca circulação — exemplo fictício"}'
```

A resposta inclui `classe`, `rotulo` e `campos`. JSON incorreto ou entradas inválidas recebem 400; tipo de conteúdo incorreto recebe 415; modelo indisponível recebe 503. A API rejeita campos ausentes, tipos incorretos, valores negativos, decimais, binários diferentes de 0/1 e números fora da representação inteira segura comum ao JavaScript.

## Extração opcional com IA generativa

A entrada manual funciona sem conta, contratação ou credencial externa. Para habilitar sugestões a partir da descrição na versão Flask:

```bash
cp .env.example .env
```

Edite **somente o arquivo local `.env`**, preenchendo `OPENAI_API_KEY` com uma credencial criada no painel do provedor e, se necessário, `OPENAI_MODEL` (padrão `gpt-4o-mini`). Reinicie o Flask. A variável também pode ser configurada no gerenciador de segredos do servidor. `.env` está excluído do versionamento. A chave nunca deve entrar no HTML, no JavaScript, no notebook, em prints ou no repositório público.

`POST /api/extrair` recebe apenas `{"descricao":"..."}` e consulta a API OpenAI para sugerir os cinco campos. Informações não declaradas retornam **`null` = desconhecido**, inclusive ausência de menção a risco. O formulário exige conferência e confirmação antes de classificar; a previsão final continua sendo da árvore. Sem chave, o endpoint responde 503; falha externa gera 502 e mantém a entrada manual disponível.

**Validação da integração:** testes de servidor com respostas simuladas e seis verificações aprovadas da interface em Chromium móvel: campos desconhecidos permanecem vazios, nenhuma previsão automática, bloqueio de campos incompletos ou sem confirmação, edição invalida a confirmação, campos confirmados permitem previsão e falha externa mantém o preenchimento manual. Evidência: [relatorios/teste_extracao_interface.json](relatorios/teste_extracao_interface.json). **Nenhuma chamada real foi realizada**, pois não havia credencial de API configurada. O uso real pode exigir contratação e envia a descrição ao provedor; neste protótipo utilize somente conteúdo fictício.

## Testes

Instale Node.js 18 ou superior para comparar a implementação JavaScript e use as dependências de desenvolvimento Python.

```bash
python -m pytest -q
python scripts/testar_navegador.py
```

O teste de paridade compara o scikit-learn, o cliente de teste Flask e o módulo JavaScript da interface sobre a base, casos aleatórios e fronteiras. O teste de navegador usa Playwright e Chromium instalado, verifica os fluxos Flask e estático com prefixo de repositório em tela de celular. O Playwright está incluído em `requirements-dev.txt`. Se o computador não tiver um navegador compatível, instale-o com `python -m playwright install chromium`, de acordo com o ambiente local.

Os testes de servidor medidos cobrem **45 casos aprovados**, incluindo resposta da API, validação e extração simulada. Os **dois testes de paridade e cenários obrigatórios** também passaram: foram comparados **2.624 casos, com zero divergências** entre scikit-learn, Flask e JavaScript. A navegação móvel também foi aprovada no Chromium 156 via Playwright em 390 × 844 pixels, nos modos Flask e estático sob o prefixo do repositório: maçaneta normal, falta de água prioritária, fiação exposta prioritária, formulário incompleto e inteiros inválidos. Os três exemplos preenchíveis, foco por teclado, ausência de rolagem horizontal e ausência de erros de console foram verificados. O modo Flask fez quatro previsões pela API; o estático fez zero chamadas à API. Evidências: [relatorios/testes_automatizados.json](relatorios/testes_automatizados.json), [captura Flask](relatorios/celular_flask.png) e [captura estática](relatorios/celular_pages_local.png).

## Publicar no GitHub Pages

A versão pública é estática: a interface informa **modo demonstração**, carrega a árvore JSON e prevê no navegador. Não existe servidor Flask nem credencial de API no GitHub Pages. Os caminhos relativos permitem hospedar em `/priorizacao-chamados-manutencao/`.

```bash
python scripts/preparar_pages.py
git add .
git commit -m "Publica protótipo acadêmico de priorização de chamados"
git push origin main
```

No GitHub, abra **Settings → Pages**, selecione a publicação a partir da branch `main`, pasta `/docs`, e salve. Depois da implantação, abra a URL retornada pelo GitHub e execute um dos exemplos fictícios. As instruções pressupõem um repositório novo, público e vazio; não é necessário alterar repositórios existentes.

**Repositório:** [GuilhermeDevSoftware/priorizacao-chamados-manutencao](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao), criado pelo titular após a credencial conectada recusar a operação `CreateRepository`. O acesso de escrita foi verificado. A disponibilização do código e do Pages deve ser confirmada pelas evidências da publicação; o link de demonstração será acrescentado quando verificado.

## Coletar e validar dados reais

Antes de sair da demonstração, combine com uma instituição parceira finalidade, responsáveis, procedimentos de emergência e critérios de prioridade. Colete chamados com um formulário padronizado e instruções claras para cada campo; mantenha desconhecidos como ausentes, sem convertê-los em zero.

Use identificadores aleatórios, remova nomes, contatos, matrículas e detalhes identificáveis da descrição e evite imagens ou dados pessoais desnecessários. Restrinja acesso, defina prazo de retenção e descarte, informe os participantes sobre uso e compartilhamento e determine com a instituição a base legal aplicável à LGPD. Consentimento, quando for a base escolhida, deve ser específico e documentado; não substitui automaticamente as demais obrigações.

Dois responsáveis com conhecimento de manutenção devem rotular os casos independentemente com a política acordada e resolver divergências com um terceiro responsável ou reunião de consenso. Registre a justificativa e audite falsos negativos. Separe chamados relacionados e períodos entre treino e teste para evitar vazamento; avalie especialmente sensibilidade, precisão, erros por contexto e carga da equipe. Comece em acompanhamento supervisionado, sem automatizar a ordem definitiva, e monitore mudanças no serviço.

## Arquivos de entrega

- `Projeto_Chamados_Manutencao.ipynb`: notebook com saídas.
- `dados/`: CSV fictício e identificação da divisão por famílias.
- `modelo/`: árvore JSON, estimador e regras legíveis.
- `frontend/` e `app.py`: interface e servidor.
- `docs/`: versão estática preparada para GitHub Pages.
- `tests/`, `scripts/` e arquivos de dependências: reprodução e verificação.
- `relatorios/`: métricas, previsões e evidências dos testes.
- `docs_academicos/`: relatório acadêmico, checklist do Classroom e roteiro de apresentação.

Não há armazenamento de chamados enviados pela interface. A entrega no Google Classroom deve ser feita pelo titular com os arquivos deste projeto; publicação em GitHub ou entrega de um ZIP não representa envio ao Classroom.
