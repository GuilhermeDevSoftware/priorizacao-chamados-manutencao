# Relatório acadêmico

**Sistema Inteligente para Priorização de Chamados de Manutenção**

Curso: Engenharia de Computação

Integrante único: **Guilherme Costa**

Prazo de entrega: **20/11/2026**

Versão: **v2 - fotos, equipes e SQLite local**

## 1. Problema e objetivo

Escolas, ONGs e pequenas instituições podem ter equipes de manutenção reduzidas. Um defeito que apresenta risco ou interrompe um serviço essencial precisa ser identificado cedo. O projeto propõe um protótipo que recebe as características de um chamado e sugere classe 0 (normal) ou 1 (prioritário), deixando a decisão final com o responsável.

O objetivo acadêmico é demonstrar a integração entre uma base estruturada, um modelo de aprendizagem de máquina, uma API, uma interface acessível e armazenamento local. A evolução v2 acrescenta foto opcional, sugestão e confirmação de equipe, histórico em SQLite e acompanhamento por status. Não houve implantação operacional nem validação com chamados reais.

## 2. Dados e critérios

A base é integralmente fictícia: 120 registros, 30 famílias de cenários e quatro variações por família. Ela inclui maçaneta frouxa em sala desocupada, falhas de água, fiação exposta, reparos estéticos e fronteiras de quantidade de pessoas e tempo de espera. Os registros possuem ID, descrição, família, origem e justificativa do rótulo.

As cinco entradas são `risco_seguranca`, `servico_essencial_interrompido`, `pessoas_afetadas`, `dias_aguardando` e `recorrente`. O alvo é `prioridade`. Risco, serviço essencial e recorrência usam valores binários; pessoas e dias são inteiros não negativos. Descrição e ID não entram no treinamento.

A classe prioritária foi atribuída se houver risco à segurança, serviço essencial interrompido, pelo menos 40 pessoas afetadas com 7 dias de espera ou recorrência com pelo menos 10 pessoas e 14 dias. Os demais exemplos recebem classe normal. Esses limiares foram definidos antes do treinamento para fins didáticos; não são normas universais. Pouca circulação não elimina risco elétrico.

## 3. Método

A validação com pandas verifica tamanho, IDs únicos, tipos, ausência de nulos, domínio dos binários, distribuição das famílias e coerência dos rótulos. A divisão usa a primeira partição fixa de `StratifiedGroupKFold` com cinco partições, embaralhamento e semente 42. Foram separados 96 registros de treino e 24 de teste, sem famílias compartilhadas. No treino há 47 normais e 49 prioritários; no teste há 10 normais e 14 prioritários. A diferença de proporções resulta da preservação dos grupos.

O modelo é `DecisionTreeClassifier(random_state=42)`. A profundidade foi ajustada com validação cruzada agrupada em quatro partições exclusivamente no treino, comparando profundidades 1, 2, 3, 4, 5, 6 e ilimitada. O critério F2 dá mais peso à sensibilidade da classe prioritária; empates favorecem a menor profundidade entre os candidatos. A profundidade escolhida e aprendida foi 6. O teste permaneceu reservado até a avaliação final.

O comparador `DummyClassifier(strategy="most_frequent")` foi ajustado no mesmo treino. Sua classe majoritária é 1. Esse comparador permite verificar se a árvore acrescenta algo além de repetir o rótulo mais comum.

## 4. Resultados medidos no teste reservado

| Modelo | Sensibilidade da classe 1 | Precisão da classe 1 | Acurácia |
| --- | ---: | ---: | ---: |
| Árvore de decisão | 100,00% | 100,00% | 100,00% |
| Classe mais frequente do treino | 100,00% | 58,33% | 58,33% |

A matriz da árvore é `[[10, 0], [0, 14]]`; a do comparador é `[[0, 10], [0, 14]]`. Linhas representam as classes reais e colunas as previstas, na ordem 0 e 1. A árvore classificou corretamente os 24 exemplos reservados. O comparador identificou todos os prioritários ao prever 1 para todos, mas marcou incorretamente os dez normais.

Não houve falsos negativos no teste reservado; portanto não existem exemplos observados desse erro para apresentar. Isso não elimina o risco de falsos negativos em dados reais ou em novas situações. Métricas, validação cruzada e previsões individuais estão nos arquivos de `relatorios/`.

## 5. Arquitetura da evolução v2

A interface responsiva continua usando HTML, CSS e JavaScript puro. A versão local distingue as ações de sugerir campos/equipe, analisar prioridade e salvar chamado. O cadastro exige descrição, local, cinco campos confirmados e equipe confirmada; a foto é opcional. A prioridade permanece legível por texto, e equipe, prioridade e status aparecem separadamente.

O Flask serve a interface e preserva `POST /api/prever`. O servidor valida os campos e percorre a árvore JSON; ao salvar, calcula novamente a classe. A fotografia e o texto não alteram diretamente a árvore. A evolução reutiliza os artefatos do treinamento original e não muda suas métricas.

A análise opcional em `POST /api/analisar` recebe descrição e foto e consulta a OpenAI com resposta estruturada: tipo de defeito, indícios observados, áreas envolvidas, equipe sugerida, justificativa, campos e informações a confirmar. Ausências permanecem desconhecidas. A foto não permite presumir pessoas afetadas, dias ou recorrência. A pessoa revisa os campos e confirma ou altera a equipe. A chave fica somente em variável de ambiente ou `.env` local ignorado pelo Git.

Sem chave ou com falha do serviço externo, uma regra textual local pode sugerir uma única equipe identificada, sem inventar campos da árvore nem afirmar que analisou a imagem. As equipes são TI, Elétrica, Hidráulica e Triagem geral; ambiguidade e múltiplas áreas resultam em Triagem geral. A equipe sugerida fica preservada mesmo se a equipe confirmada for corrigida. Cadastrar não depende da disponibilidade da API externa.

O armazenamento usa `sqlite3`, da biblioteca padrão do Python, com criação automática do banco e consultas parametrizadas. Cada chamado recebe ID, descrição, local, data de abertura UTC, campos da árvore, prioridade, equipe sugerida, equipe confirmada e status. A justificativa e a análise disponível também são guardadas para consulta. O status começa em Aberto e pode mudar para Em atendimento ou Resolvido.

O banco fica em `instance/chamados.sqlite3`; fotos ficam em `instance/uploads/`, e somente o caminho relativo é armazenado no SQLite. São aceitos JPEG, PNG e WebP até 5 MiB e 25 megapixels, com verificação da decodificação, correção de orientação, remoção de metadados e normalização para JPEG com lado máximo de 2.048 pixels. O nome é gerado pelo servidor. Banco, fotos cadastradas e segredos ficam fora do repositório e da publicação.

O painel permite listar e consultar chamados, filtrar equipe confirmada, prioridade e status e atualizar equipe/status. Na demonstração estática do GitHub Pages, a árvore roda em JavaScript e o painel usa quatro exemplos fictícios fixos somente para consulta e filtros. A prévia de foto pode ocorrer no navegador; análise multimodal, gravação e atualização exigem Flask em execução.

## 6. Verificação e local de execução

O treinamento e a execução do notebook ocorreram no ambiente local Codex Cloud, com Python 3.12 e scikit-learn 1.8.0. As dez células de código foram executadas em ordem, sem erro, e as saídas foram salvas. O notebook é autocontido e compatível com o Colab; não se afirma execução no serviço Google.

As evidências históricas da primeira versão registram 47 testes aprovados e 2.624 casos de paridade sem divergências entre scikit-learn, Flask e JavaScript. O Chromium 156 foi usado em tela de 390 x 844 pixels, tanto no Flask quanto na demonstração pública. Essas verificações documentam a v1 e não validam por si só as funções adicionadas na evolução.

A evolução v2 passou em 110 testes pytest, incluindo a paridade de 2.624 casos sem divergências. No Chromium 156 em 390 x 844, foram cadastrados quatro chamados fictícios: fiação exposta com imagem sintética, vazamento sem foto, TI e caso com duas áreas. A prévia e remoção da imagem, rejeição de arquivo inválido, confirmação, revisão de equipe e status e filtros combinados passaram. Depois de encerrar o processo Flask e iniciar outro com o mesmo SQLite e uploads, os quatro registros permaneceram disponíveis e a foto manteve o mesmo SHA256. O painel estático com quatro exemplos fixos foi verificado sob o prefixo do repositório. Não houve erros de console ou rolagem horizontal. As evidências estão em relatorios/testes_evolucao_navegador.json.

Sete verificações de interface da análise multimodal passaram com respostas simuladas, incluindo campos desconhecidos, confirmação humana, falha externa e preservação do preenchimento manual. Não havia chave configurada e nenhuma chamada real à OpenAI foi realizada. A câmera física não foi exercitada; a seleção de arquivo, prévia, remoção e o atributo de captura móvel foram verificados. O registro está em relatorios/teste_extracao_interface_v2.json.

## 7. Limitações e continuidade

A base pequena, fictícia e rotulada por regras explícitas explica o desempenho perfeito observado. Esse resultado mede a reprodução da política didática nesses exemplos e não estima a segurança ou utilidade em uma instituição real. A separação por família evita misturar variações de um cenário, mas não torna os dados independentes de todos os padrões compartilhados. A classificação binária também não representa sozinha critérios como disponibilidade de equipe, custo, materiais e procedimentos de emergência.

Para avançar, é necessário firmar parceria com uma instituição e padronizar a coleta. Devem ser minimizados e anonimizados nomes, contatos e detalhes identificáveis, com controle de acesso, retenção definida e base legal para o tratamento. A rotulagem deve ser feita por dois avaliadores com conhecimento técnico e consenso para divergências. A divisão futura deve separar chamados relacionados e períodos, preservando dados realmente novos para teste. Um piloto supervisionado deverá monitorar falsos negativos, diferenças entre contextos e a carga da equipe antes de qualquer uso operacional.

## 8. Entrega e publicação

Os arquivos da evolução incluem notebook executado, CSV fictício, árvore JSON, código Flask e SQLite, interface, validação de fotos, encaminhamento por equipe, painel, dependências e testes. Guilherme Costa é o único integrante. O pacote público não inclui banco local, fotos cadastradas nem credenciais.

O projeto utiliza o [repositório público existente](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao) e a [demonstração no GitHub Pages](https://guilhermedevsoftware.github.io/priorizacao-chamados-manutencao/). A primeira entrega permanece preservada como registro histórico; a evolução tem [pacote próprio v2.0.0](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao/releases/tag/v2.0.0). A demonstração pública usa somente exemplos fictícios e não hospeda o Flask nem o banco.

O [link para abrir o notebook no Colab](https://colab.research.google.com/github/GuilhermeDevSoftware/priorizacao-chamados-manutencao/blob/main/Projeto_Chamados_Manutencao.ipynb) disponibiliza a versão do GitHub. O notebook entregue contém as saídas verificadas da execução local.

Para demonstrar a persistência, é necessário iniciar o Flask no computador, cadastrar um chamado, fechar o servidor e reiniciá-lo usando a mesma pasta `instance/`. Banco e uploads precisam ser mantidos juntos no backup. A entrega ao Google Classroom é realizada pelo titular; este pacote não representa envio à atividade.
