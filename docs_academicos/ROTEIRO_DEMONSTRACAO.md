# Roteiro de demonstração da evolução v2

**Integrante único:** Guilherme Costa

**Projeto:** Sistema Inteligente para Priorização de Chamados de Manutenção

## Preparação

Instale as dependências e execute `python app.py`. Abra `http://127.0.0.1:5000`. Use somente exemplos fictícios durante a apresentação. A chave de IA é opcional; sem ela o cadastro manual e a sugestão textual local de equipe funcionam.

Explique a diferença: o [GitHub Pages](https://guilhermedevsoftware.github.io/priorizacao-chamados-manutencao/) tem previsão no navegador e painel com exemplos fixos. Salvar chamados, analisar fotos com IA e atualizar atendimentos são funções da execução Flask local.

## Apresentação de aproximadamente sete minutos

1. **Objetivo:** identificar riscos e interrupções essenciais cedo, apoiando a pessoa que organiza a manutenção.
2. **IA de prioridade:** apresentar os cinco campos, o CSV fictício, o notebook e a árvore compartilhada entre Flask e JavaScript. Informar a divisão 96/24 por famílias e as limitações das métricas perfeitas na amostra sintética.
3. **Foto opcional:** preencher descrição e local, selecionar uma imagem sintética identificada de fiação exposta, conferir a prévia e demonstrar a remoção. Em celular compatível existe a opção de captura.
4. **Análise e triagem:** solicitar sugestões, identificar se a origem é IA ou regra local, completar desconhecidos e confirmar ou corrigir a equipe. A árvore continua responsável pela classe.
5. **Cadastro:** mostrar que Analisar chamado apenas prevê e Salvar chamado cria ID e status Aberto. Mostrar equipe responsável, prioridade e status em campos separados.
6. **Painel:** filtrar equipe, prioridade e status; abrir um detalhe e alterar a equipe confirmada e o status. Conferir que a equipe sugerida original continua registrada.
7. **Persistência:** encerrar o Flask, iniciar novamente com a mesma pasta `instance/` e consultar o chamado pelo ID. Explicar que SQLite é local e que fotos ficam fora do banco, com seus caminhos registrados.
8. **Limites:** mostrar que o Pages não grava chamados, que não se publica o banco ou os uploads e que a análise externa é opcional e sujeita a revisão.

## Casos para apresentar

| Caso fictício | Campos confirmados [risco, essencial, pessoas, dias, recorrente] | Equipe esperada | Prioridade esperada |
| --- | --- | --- | --- |
| Fiação exposta em área pouco usada, com imagem sintética de teste | [1, 0, 1, 0, 0] | Elétrica | Prioritário |
| Vazamento em torneira auxiliar, sem foto, sem piso escorregadio e sem interrupção essencial | [0, 0, 5, 1, 0] | Hidráulica | Normal |
| Computador auxiliar com defeito e alternativa disponível | [0, 0, 1, 0, 0] | TI | Normal |
| Computador sem conexão e tomada danificada: envolve duas áreas | [1, 0, 2, 0, 0] | Triagem geral | Prioritário |

As expectativas acima são exemplos da política didática com campos confirmados. Não preencha desconhecidos como zero para obter um resultado. Uma fotografia não informa por si só pessoas afetadas, tempo de espera ou recorrência.

## Respostas a perguntas prováveis

**Qual IA decide a prioridade?** A árvore de decisão treinada com scikit-learn. A integração multimodal apenas sugere informações e equipe.

**Qual banco foi usado?** SQLite, acessado pelo módulo `sqlite3` do Python. O arquivo é local e criado automaticamente; não exige servidor de banco separado.

**Ao clicar em Analisar, salva?** Não. A gravação acontece em Salvar chamado, após a confirmação dos campos e da equipe.

**As fotos ficam no SQLite?** Não. Ficam em `instance/uploads/`, com nome gerado pelo servidor; o banco guarda o caminho relativo. Banco e uploads devem ser copiados juntos para backup.

**Funciona sem API de IA?** O cadastro e a prioridade continuam funcionando com dados manuais. Uma regra local pode sugerir equipe pela descrição e identifica sua origem; não afirma analisar a foto.

**Por que 100% no teste?** O conjunto é pequeno e fictício, rotulado por uma política explícita. Acertar os 24 exemplos reservados não comprova desempenho em uma instituição real.

**Quem decide o atendimento?** O responsável pela manutenção, que revisa contexto, dados e encaminhamento.
