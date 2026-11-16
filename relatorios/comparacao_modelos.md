# Comparação dos modelos

CV agrupada repetida somente nos dados de desenvolvimento. Valores: média ± desvio-padrão entre repetições; IC95% por bootstrap de famílias.

| Modelo | Sensibilidade | Precisão | F1 | F2 | Acurácia |
| --- | --- | --- | --- | --- | --- |
| Dummy | 0.5510 ± 0.0000 [0.4450; 0.6679] | 0.4500 ± 0.0000 [0.2825; 0.6206] | 0.4954 ± 0.0000 [0.3561; 0.6013] | 0.5273 ± 0.0000 [0.4117; 0.6191] | 0.4271 ± 0.0000 [0.3521; 0.5042] |
| Regras | 1.0000 ± 0.0000 [1.0000; 1.0000] | 1.0000 ± 0.0000 [1.0000; 1.0000] | 1.0000 ± 0.0000 [1.0000; 1.0000] | 1.0000 ± 0.0000 [1.0000; 1.0000] | 1.0000 ± 0.0000 [1.0000; 1.0000] |
| Arvore | 0.9816 ± 0.0244 [0.9588; 0.9958] | 0.9628 ± 0.0278 [0.9228; 0.9874] | 0.9718 ± 0.0170 [0.9446; 0.9885] | 0.9776 ± 0.0194 [0.9551; 0.9918] | 0.9708 ± 0.0176 [0.9531; 0.9854] |
| Logistica | 0.7082 ± 0.0099 [0.4635; 0.8810] | 0.9285 ± 0.0233 [0.8184; 1.0000] | 0.8033 ± 0.0079 [0.6025; 0.9154] | 0.7433 ± 0.0077 [0.5126; 0.8922] | 0.8229 ± 0.0085 [0.7208; 0.9167] |
| RandomForest | 1.0000 ± 0.0000 [1.0000; 1.0000] | 0.9705 ± 0.0138 [0.9242; 1.0000] | 0.9850 ± 0.0070 [0.9603; 1.0000] | 0.9939 ± 0.0029 [0.9836; 1.0000] | 0.9844 ± 0.0074 [0.9625; 1.0000] |

O teste reservado é relatado separadamente no JSON e no CSV. A árvore do aplicativo foi preservada.

Bootstrap e desvio-padrão condicionados a somente 24 famílias fictícias de desenvolvimento; não medem desempenho real.
Repetir partições não cria novos dados independentes e o intervalo não incorpora todas as incertezas da geração sintética.
A profundidade 6 já havia sido escolhida anteriormente; a CV avalia configurações fixas, não reavalia todo o processo de seleção.
O baseline de regras conhece a função que gerou os rótulos: serve de referência de consistência, não de validação externa.
Com política conhecida e estável, regras explícitas resolvem esta tarefa sem necessidade de ML; os modelos aprendidos são experimentos acadêmicos.
