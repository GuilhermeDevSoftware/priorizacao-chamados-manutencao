# Relatório acadêmico

**Sistema Inteligente para Priorização de Chamados de Manutenção**  
Curso: Engenharia de Computação  
Integrante único: **Guilherme Costa**  
Prazo de entrega: **20/11/2026**

## 1. Problema e objetivo

Escolas, ONGs e pequenas instituições podem ter equipes de manutenção reduzidas. Um defeito que apresenta risco ou interrompe um serviço essencial precisa ser identificado cedo. O projeto propõe um protótipo que recebe as características de um chamado e sugere classe 0 (normal) ou 1 (prioritário), deixando a decisão final com o responsável.

O objetivo acadêmico é demonstrar a integração entre uma base estruturada, um modelo de aprendizagem de máquina, uma API e uma interface acessível. Não houve implantação operacional nem validação com chamados reais.

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

## 5. Arquitetura do protótipo

A interface responsiva usa HTML, CSS e JavaScript puro e oferece campos rotulados, validação, exemplos fictícios e resultado textual. A prioridade permanece legível independentemente de cor. A descrição é opcional. Nenhum chamado é persistido pelo aplicativo.

Na execução local, o Flask serve a interface e `POST /api/prever`. O servidor valida os dados e percorre a árvore exportada em JSON para devolver classe, rótulo e campos. Na publicação estática, a interface informa o modo demonstração e executa em JavaScript a mesma árvore, sem necessidade de um servidor Python. Os caminhos relativos permitem o uso sob o nome do repositório.

A integração opcional `POST /api/extrair` solicita a uma API generativa sugestões dos cinco campos. Ausências são representadas por `null`. As sugestões precisam de revisão e confirmação, e a classificação continua sendo feita pela árvore. A credencial é configurada apenas no servidor por variável de ambiente. Sem credencial ou com erro externo, o preenchimento manual permanece disponível.

## 6. Verificação e local de execução

O treinamento e a execução do notebook ocorreram no ambiente local Codex Cloud, com Python 3.12 e scikit-learn 1.8.0. As dez células de código foram executadas em ordem, sem erro, e as saídas foram salvas. O notebook é autocontido e compatível com o Colab, mas a automação da sessão autenticada do navegador não estava disponível; não se afirma execução no serviço Google.

Foram medidos 45 testes aprovados da API e da extração simulada e dois testes aprovados de paridade e cenários obrigatórios. A comparação entre scikit-learn, Flask e JavaScript avaliou 2.624 casos sem divergências. A navegação móvel foi aprovada no Chromium 156 via Playwright em 390 × 844 pixels, tanto no Flask quanto na versão estática sob o prefixo do repositório. Foram verificados os três exemplos preenchíveis, foco útil por teclado, ausência de rolagem horizontal e ausência de erros de console. O navegador fez quatro previsões pela API no Flask e nenhuma chamada à API no modo estático. As evidências estão em `relatorios/testes_automatizados.json` e nas capturas de celular. A extração foi também verificada em seis cenários de interface com respostas simuladas: desconhecidos continuam vazios, não ocorre previsão automática, campos incompletos ou sem confirmação são bloqueados, editar desfaz a confirmação, confirmar permite prever e uma falha externa mantém a entrada manual. Nenhuma chamada real ao provedor foi realizada por ausência de credencial. O registro está em `relatorios/teste_extracao_interface.json`.

Casos funcionais medidos e aprovados nos dois modos: maçaneta frouxa em sala desocupada → normal; falta de água na escola → prioritário; fiação exposta com pouca circulação → prioritário; formulário incompleto → validação sem previsão; valores -1 e 1,5 → rejeição por validação.

## 7. Limitações e continuidade

A base pequena, fictícia e rotulada por regras explícitas explica o desempenho perfeito observado. Esse resultado mede a reprodução da política didática nesses exemplos e não estima a segurança ou utilidade em uma instituição real. A separação por família evita misturar variações de um cenário, mas não torna os dados independentes de todos os padrões compartilhados. A classificação binária também não representa sozinha critérios como disponibilidade de equipe, custo, materiais e procedimentos de emergência.

Para avançar, é necessário firmar parceria com uma instituição e padronizar a coleta. Devem ser minimizados e anonimizados nomes, contatos e detalhes identificáveis, com controle de acesso, retenção definida e base legal para o tratamento. A rotulagem deve ser feita por dois avaliadores com conhecimento técnico e consenso para divergências. A divisão futura deve separar chamados relacionados e períodos, preservando dados realmente novos para teste. Um piloto supervisionado deverá monitorar falsos negativos, diferenças entre contextos e a carga da equipe antes de qualquer uso operacional.

## 8. Entrega e publicação

Os arquivos incluem notebook executado, CSV, árvore JSON, código Flask, interface estática, dependências, testes e instruções de reprodução. Guilherme Costa é o único integrante.

O repositório público novo [GuilhermeDevSoftware/priorizacao-chamados-manutencao](https://github.com/GuilhermeDevSoftware/priorizacao-chamados-manutencao) foi criado pelo titular após a credencial conectada recusar sua criação pela falta da permissão `CreateRepository`. O acesso de escrita foi verificado. O estado da publicação do código e do GitHub Pages será registrado após a verificação correspondente. Os arquivos estão organizados para anexação ao Google Classroom; não foi realizado envio à plataforma.
