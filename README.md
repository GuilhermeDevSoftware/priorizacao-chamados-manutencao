# Sistema Inteligente para Priorização de Chamados de Manutenção

Projeto acadêmico de Engenharia de Computação. **Integrante único: Guilherme Costa.** Prazo informado: **20/11/2026**. Evolução v2: fotos, equipes e armazenamento local.

Protótipo para escolas, ONGs e pequenas instituições. A árvore de decisão treinada com scikit-learn sugere **0 = normal** ou **1 = prioritário**. A versão local também cadastra chamados com foto opcional, sugere uma equipe e mantém o histórico em SQLite. O responsável confirma os dados, escolhe a equipe e decide a ordem do atendimento.

**Todos os 120 chamados são fictícios.** O sistema não foi validado em uma instituição real, e os resultados apresentados não comprovam segurança ou eficácia em uso operacional. Em situações de risco, a instituição deve aplicar seus procedimentos de emergência e avaliação técnica.

## Executar no computador

Use Python 3.12 e Node.js 18 ou superior para os testes de paridade. Os comandos abaixo são executados na raiz do projeto:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python app.py
```

No Windows, ative com `.venv\Scripts\activate`. Abra **http://127.0.0.1:5000**. Para outra porta em Linux/macOS, use `PORT=5055 python app.py`. O Flask serve a interface e a API local. O SQLite usa o módulo `sqlite3` da biblioteca padrão; não exige instalar ou manter um servidor de banco. A validação de imagens usa Pillow.

Para apenas executar o aplicativo e retreinar, instale `requirements.txt`. As dependências de desenvolvimento incluem testes e execução de notebooks. Nenhum serviço de hospedagem adicional ou login é necessário nesta versão local.

## Usar o protótipo local

1. Escreva a descrição e informe o local do defeito. Para salvar, ambos são obrigatórios.
2. Opcionalmente, escolha uma foto da galeria ou tire uma foto em um celular compatível. Confira a prévia e remova o arquivo se necessário.
3. Solicite sugestões de campos e equipe ou preencha os campos manualmente. A análise com IA usa a descrição e a foto quando a integração estiver configurada.
4. Complete as informações desconhecidas e revise os cinco campos da árvore. Confirme ou altere a equipe sugerida.
5. **Analisar chamado** mostra a prioridade sem gravar um cadastro. **Salvar chamado** grava o registro e a foto no computador, após confirmação explícita.
6. No painel, filtre por equipe responsável, prioridade e status. Abra um chamado para consultar seus dados e foto e atualizar equipe ou status.

Os campos binários aceitam `0` ou `1`; pessoas e dias são inteiros não negativos. Campos em branco são desconhecidos e impedem a previsão e o cadastro. A prioridade é calculada novamente pelo servidor ao salvar. Alterar a equipe ou o status não recalcula a prioridade nem apaga a sugestão original.

Descrição e foto ajudam a sugerir informações; não entram diretamente na árvore. Alterar os dados invalida a confirmação anterior. A árvore continua usando exclusivamente os cinco campos numéricos confirmados.

## Equipes e status

| Equipe | Exemplos |
| --- | --- |
| TI | Computador com defeito, impressora sem conexão, internet indisponível |
| Elétrica | Fiação exposta, tomada danificada, falha de iluminação |
| Hidráulica | Vazamento, torneira quebrada, falta de água |
| Triagem geral | Área não identificada, descrição ambígua ou várias áreas envolvidas |

A interface separa **equipe sugerida**, justificativa e **equipe confirmada**. O responsável pode corrigir a sugestão; o painel filtra a equipe confirmada, que representa o encaminhamento atual. A equipe não determina a prioridade.

O status inicial é **Aberto** e pode ser alterado para **Em atendimento** ou **Resolvido**. Equipe, prioridade e status são apresentados separadamente.

## SQLite, fotos e persistência

O banco é criado automaticamente em `instance/chamados.sqlite3`; as fotos ficam em `instance/uploads/`. Não há gravação de imagens dentro do SQLite: o banco guarda apenas o caminho relativo. A aplicação usa consultas parametrizadas e nomes de arquivos gerados pelo servidor.

Cada registro contém ID, descrição, local, data de abertura em UTC, os cinco campos da árvore, prioridade sugerida, equipe sugerida, justificativa, equipe confirmada e status. A análise estruturada, quando houver, é preservada para consulta. A data de abertura e a prioridade são definidas pelo servidor. O SQLite inicia vazio; os exemplos fixos do Pages não são importados automaticamente. Dias aguardando e prioridade ficam como valores confirmados no cadastro, sem reajuste automático pelo relógio.

A foto é opcional. São aceitos **JPEG, PNG e WebP, até 5 MiB e 25 megapixels**. Se o celular exportar HEIC/HEIF, converta a foto para JPEG antes de anexar. O servidor verifica a decodificação real da imagem, corrige orientação, remove metadados e normaliza para JPEG com lado máximo de 2.048 pixels. A prévia não representa salvamento. Solicitar a análise também não grava o chamado: a foto só vai para a pasta de uploads no cadastro válido.

Os dados continuam disponíveis ao fechar e iniciar novamente o Flask. Para backup, pare o aplicativo e copie **toda a pasta `instance/`**, preservando banco e uploads juntos. Para restaurar, recoloque essa pasta no mesmo projeto antes de iniciar o Flask. A fábrica da aplicação permite configurar `DATABASE_PATH` e `UPLOAD_FOLDER` em testes ou outra execução local.

`instance/`, bancos locais, uploads e `.env` ficam fora do Git e do pacote público. A demonstração do Pages não recebe registros do SQLite.

## Dados e política de rotulagem

A base CSV de treinamento é separada do SQLite usado nos novos cadastros: salvar chamados não retreina a IA automaticamente. A base reproduzível reúne **120 registros em 30 famílias**, com quatro variações de cada cenário. Contém problemas de baixo impacto, alto impacto e fronteiras dos limiares. ID, descrição, família, origem e justificativa documentam os exemplos; somente os cinco campos numéricos são entradas do modelo.

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

[Projeto_Chamados_Manutencao.ipynb](Projeto_Chamados_Manutencao.ipynb) incorpora a geração da base e todo o processo de validação, divisão, ajuste, avaliação e exportação. [Abrir o notebook no Google Colab](https://colab.research.google.com/github/GuilhermeDevSoftware/priorizacao-chamados-manutencao/blob/main/Projeto_Chamados_Manutencao.ipynb) permite carregar a versão do repositório; esse link não comprova execução no serviço Google. Ele não depende de upload de um CSV externo e permanece compatível com o Google Colab. É possível abri-lo em `https://colab.research.google.com/`, escolher **Arquivo → Fazer upload de notebook** e depois **Ambiente de execução → Executar tudo**.

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

## Árvore compartilhada e APIs

`modelo/arvore.json` contém ordem dos atributos, classes, nós, limiares, filhos, contagens e metadados. Flask e JavaScript percorrem essa mesma árvore com a conversão numérica usada pelo scikit-learn. `modelo/arvore.joblib` preserva o estimador para os testes de paridade. A evolução v2 não retreinou nem trocou o modelo.

| Rota | Uso |
| --- | --- |
| `POST /api/prever` | JSON com os cinco campos e descrição opcional; devolve `classe`, `rotulo` e `campos`, sem cadastrar. |
| `POST /api/analisar` | Multipart com `descricao` e `foto` opcional; sugere campos e equipe, sem cadastrar. |
| `POST /api/chamados` | Multipart com `dados` em JSON e `foto` opcional; cadastra após confirmação e devolve o registro com HTTP 201. |
| `GET /api/chamados` | Lista; filtros combináveis `equipe`, `prioridade` e `status`. |
| `GET /api/chamados/<id>` | Consulta um registro. |
| `PATCH /api/chamados/<id>` | JSON para alterar somente `equipe_confirmada` e/ou `status`. |
| `GET /api/chamados/<id>/foto` | Consulta a imagem associada ao registro. |
| `POST /api/extrair` | Compatibilidade com a extração textual v1; recebe somente `descricao` em JSON. |

Exemplo de cadastro manual sem foto e sem chamada à IA:

```bash
curl -X POST http://127.0.0.1:5000/api/chamados \
  -F 'dados={"descricao":"Vazamento fictício em torneira auxiliar","local":"Pátio - exemplo fictício","risco_seguranca":0,"servico_essencial_interrompido":0,"pessoas_afetadas":5,"dias_aguardando":1,"recorrente":0,"equipe_confirmada":"Hidráulica","confirmado":true}'
```

Para anexar a imagem, acrescente `-F 'foto=@caminho/imagem.jpg'`. Ao usar o resultado de uma análise, `dados` também pode incluir `analise` com o objeto estruturado revisado. O servidor valida os dados e calcula a prioridade; o cliente não escolhe ID, data, caminho da foto, prioridade ou status inicial.

JSON incorreto e campos inválidos recebem 400, tipo de conteúdo incorreto recebe 415, limite de tamanho recebe 413 e registro inexistente recebe 404. As rotas legadas de JSON mantêm o limite de 32 KB. Fotos têm o limite próprio de 5 MiB, dentro do limite multipart de 6 MiB.

## IA multimodal opcional

Para configurar a integração no Flask:

```bash
cp .env.example .env
```

Edite **somente o `.env` local**, preenchendo `OPENAI_API_KEY` e, se necessário, `OPENAI_MODEL` (padrão `gpt-4o-mini`). Reinicie o Flask. A chave também pode ser definida como variável de ambiente do servidor. Ela não deve entrar no HTML, JavaScript, notebook, capturas, banco ou repositório.

Ao solicitar a análise configurada, o Flask envia a descrição e a imagem normalizada, se houver, à OpenAI. A resposta estruturada reúne tipo de defeito, indícios observados, áreas envolvidas, equipe sugerida, justificativa, campos sugeridos e informações a confirmar. O formulário informa esse envio antes da ação.

Informações ausentes permanecem **`null` = desconhecido**. Pessoas afetadas, dias e recorrência não são presumidos por uma foto. As sugestões precisam de revisão humana e a árvore calcula a prioridade a partir dos campos confirmados.

Sem chave, em timeout ou diante de resposta externa inválida, `/api/analisar` devolve uma alternativa identificada como **regra local**, com aviso. Essa alternativa sugere a equipe pela descrição quando reconhece uma única área; ambiguidade ou várias áreas resultam em Triagem geral. Ela não afirma que analisou a imagem e não inventa valores para os cinco campos. O cadastro manual permanece disponível e **salvar não chama a API externa**.

A rota textual legada `/api/extrair` mantém seu contrato: sem chave responde 503 e falha externa responde 502. O formulário evoluído usa `/api/analisar` e sua alternativa local.

**Validação externa da v2:** não havia chave configurada e nenhuma chamada real à OpenAI foi realizada. A integração multimodal foi testada com respostas simuladas; o modo sem chave foi exercitado de ponta a ponta, com cadastro manual e sugestão textual local. A câmera física não foi exercitada: os testes móveis verificaram seleção, prévia, remoção e o atributo de captura do formulário.

## Testes

Instale as dependências de desenvolvimento e Node.js 18 ou superior:

```bash
python -m pytest -q
python scripts/testar_evolucao.py
python scripts/testar_extracao_interface.py
```

O teste de navegador usa Playwright. Se necessário, instale um Chromium com `python -m playwright install chromium`; também é possível selecionar o navegador pelo `CHROMIUM_PATH`.

**Resultados medidos da v2:** 110 testes pytest aprovados, incluindo os 2.624 casos de paridade sem divergências. No Chromium 156 em 390 × 844, os quatro cenários foram cadastrados, equipe e status foram alterados, os filtros combinados retornaram o registro esperado e os quatro chamados e a foto permaneceram íntegros após encerrar o processo Flask e iniciar outro com o mesmo banco. Prévia/remoção e arquivo inválido também foram verificados, sem erros de console ou rolagem horizontal. O painel estático exibiu quatro exemplos fixos, com filtros e edição bloqueada. Evidência: [teste integrado](relatorios/testes_evolucao_navegador.json). As [sete verificações simuladas da interface multimodal](relatorios/teste_extracao_interface_v2.json) também passaram, incluindo informações desconhecidas, confirmação e preservação dos campos manuais no fallback.

As evidências históricas da v1 registram **47 testes aprovados** e **2.624 casos de paridade sem divergências**, além dos fluxos móveis em Chromium 156, 390 × 844. Elas documentam a primeira versão, que ainda não tinha SQLite nem fotos; não comprovam os recursos novos. Os artefatos históricos estão em `relatorios/testes_automatizados.json`, `relatorios/teste_pages_publico.json` e nas capturas correspondentes.

## Flask local e GitHub Pages

| Recurso | Flask local | GitHub Pages |
| --- | --- | --- |
| Prever prioridade pela árvore | Sim, pela API | Sim, no navegador |
| Selecionar foto e mostrar prévia | Sim | Sim, somente no navegador |
| Analisar descrição e foto com IA | Opcional, com chave | Não |
| Sugerir equipe pela análise/regra local | Sim | Apenas sugestões dos exemplos fictícios |
| Salvar chamado e foto | Sim, SQLite e uploads locais | Não |
| Painel e filtros | Registros do SQLite | Quatro exemplos fictícios fixos |
| Atualizar equipe e status | Sim | Não, painel somente leitura |

A página pública informa **modo demonstração** e identifica as funções que precisam do Flask. Nenhum cadastro local, banco ou upload é copiado para a publicação. Os caminhos relativos permitem o uso sob `/priorizacao-chamados-manutencao/`.

Para atualizar a versão estática a partir do código:

```bash
python scripts/preparar_pages.py
git add .
git commit -m "Evolui chamados com fotos, equipes e SQLite local"
git push origin main
```

Antes de enviar, confira `git status` para garantir que a pasta `instance/` e o `.env` não estão incluídos. Em uma cópia clonada, preserve o remoto. No GitHub Pages, a fonte é branch `main`, pasta `/docs`. O preparo usa arquivos estáticos permitidos, nunca a pasta `instance/`.

Links do projeto: [repositório público](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao), [demonstração no GitHub Pages](https://guilhermedevsoftware.github.io/priorizacao-chamados-manutencao/) e [notebook para abrir no Colab](https://colab.research.google.com/github/GuilhermeDevSoftware/priorizacao-chamados-manutencao/blob/main/Projeto_Chamados_Manutencao.ipynb). O notebook contém saídas da execução local, não da execução no serviço Google.

A [entrega v1](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao/releases/tag/entrega-academica-2026-11-15) permanece como registro histórico. A evolução tem [pacote e evidências próprios na versão v2.0.0](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao/releases/tag/v2.0.0). A prévia privada no Sites é uma cópia independente da demonstração e não hospeda o Flask nem o SQLite.

## Coletar e validar dados reais

Antes de sair da demonstração, combine com uma instituição parceira finalidade, responsáveis, procedimentos de emergência e critérios de prioridade. Colete chamados com um formulário padronizado e instruções claras para cada campo; mantenha desconhecidos como ausentes, sem convertê-los em zero.

Use identificadores aleatórios, remova nomes, contatos, matrículas e detalhes identificáveis da descrição e evite imagens ou dados pessoais desnecessários. Restrinja acesso, defina prazo de retenção e descarte, informe os participantes sobre uso e compartilhamento e determine com a instituição a base legal aplicável à LGPD. Consentimento, quando for a base escolhida, deve ser específico e documentado; não substitui automaticamente as demais obrigações.

Dois responsáveis com conhecimento de manutenção devem rotular os casos independentemente com a política acordada e resolver divergências com um terceiro responsável ou reunião de consenso. Registre a justificativa e audite falsos negativos. Separe chamados relacionados e períodos entre treino e teste para evitar vazamento; avalie especialmente sensibilidade, precisão, erros por contexto e carga da equipe. Comece em acompanhamento supervisionado, sem automatizar a ordem definitiva, e monitore mudanças no serviço.

## Arquivos de entrega

Baixe a [entrega v2.0.0](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao/releases/tag/v2.0.0), com ZIP e anexos. Os arquivos da v1 permanecem preservados:

- `Projeto_Chamados_Manutencao.ipynb`: notebook executado e autocontido.
- `dados/` e `modelo/`: CSV fictício, divisão, árvore JSON e estimador.
- Código Flask, módulos locais e `frontend/`: cadastro, análise, encaminhamento e painel.
- `docs/`: demonstração estática com exemplos fixos.
- `tests/`, `scripts/` e dependências: reprodução e verificação.
- `relatorios/`: métricas originais e evidências identificadas por versão.
- `docs_academicos/`: relatório, checklist do Classroom e roteiro de apresentação.

O pacote público exclui o banco, os uploads cadastrados, ambientes virtuais e credenciais. O envio ao Google Classroom deve ser feito pelo titular; disponibilizar o projeto no GitHub não representa envio à atividade.

Para gerar novamente um ZIP somente com os arquivos do commit atual, excluindo dados locais e entregas anteriores:

```bash
python scripts/empacotar_entrega.py --saida ../Entrega_v2.zip
```
