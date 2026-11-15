# Base de chamados fictícios

**Todos os 120 registros são inteiramente fictícios.** Autor: Guilherme Costa. Não há informações de pessoas reais ou de uma instituição parceira. A geração é determinística em `scripts/treinar.py` e está incorporada no notebook. São 30 famílias com quatro variações; o conjunto reservado mantém cada família inteira em um só lado da divisão.

## Dicionário

| Coluna | Definição |
|---|---|
| `id` | Identificador fictício único; não entra no modelo |
| `familia_cenario` | Família usada para impedir vazamento entre variações no treino/teste e na validação cruzada; não entra no modelo |
| `descricao` | Contexto fictício; somente documentação, não é entrada da árvore |
| `risco_seguranca` | 0: risco não identificado na avaliação humana; 1: risco identificado |
| `servico_essencial_interrompido` | 0: serviço essencial não interrompido; 1: interrompido |
| `pessoas_afetadas` | Contagem inteira não negativa de pessoas afetadas |
| `dias_aguardando` | Dias inteiros não negativos desde a abertura |
| `recorrente` | 0: não recorrente; 1: recorrente |
| `prioridade` | Alvo: 0 = normal, 1 = prioritário |
| `justificativa_rotulo` | Critérios aplicados antes do treino |
| `origem` | Sempre `fictícia` |

Um campo não informado é **desconhecido**, não zero. A base didática não possui campos ausentes. A aplicação exige confirmação e preenchimento das cinco entradas antes da classificação.

## Critérios de rotulagem definidos antes do treino

Um chamado é prioritário se ao menos uma condição for verdadeira:

1. Há risco à segurança, independentemente do número de pessoas ou da circulação.
2. Há interrupção de serviço essencial.
3. Há pelo menos 40 pessoas afetadas **e** espera de pelo menos 7 dias.
4. Há recorrência, pelo menos 10 pessoas afetadas **e** espera de pelo menos 14 dias.

Os demais chamados são normais. Os critérios 3 e 4 são escolhas pedagógicas arbitrárias que permitem estudar casos limítrofes, não recomendações técnicas. Água, saneamento, energia, alimentação e acesso indispensável podem ser essenciais; um equipamento auxiliar com alternativa não é automaticamente essencial. Risco deve ser avaliado pelo responsável habilitado.

Exemplos incluídos: maçaneta frouxa em sala desocupada sem risco de aprisionamento; falta de água na escola; fiação exposta em local com pouca circulação; 39/40 pessoas, 6/7 dias, 9/10 pessoas e 13/14 dias.

## Divisão e limitações

Há 57 registros normais e 63 prioritários. O primeiro fold de `StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)` determina a divisão: 96 registros e 24 famílias no treino; 24 registros e 6 famílias no teste. O treino contém 47 normais e 49 prioritários; o teste contém 10 normais e 14 prioritários. A proporção de prioritários é 52,5% na base, 51,04% no treino e 58,33% no teste. A indivisibilidade das famílias limita a estratificação exata. A partição foi fixada antes da avaliação, sem buscar um teste favorável.

A profundidade é escolhida por validação cruzada agrupada de quatro folds somente no treino. O modelo exportado permanece treinado nos 96 registros, permitindo reproduzir a avaliação reservada. Não há retreino nos 120 após avaliar. Famílias diferentes podem ter atributos numéricos iguais; separar famílias reduz vazamento de variações sem eliminar a simplicidade da distribuição sintética.

Os rótulos reproduzem regras definidas pelo autor; as métricas avaliam a aproximação dessas regras em uma amostra artificial. Não medem desempenho real nem comprovam segurança. Nenhum dado externo foi coletado para esta entrega.
