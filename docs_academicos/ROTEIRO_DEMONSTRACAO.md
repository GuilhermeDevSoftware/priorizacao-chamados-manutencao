# Roteiro de demonstração

**Integrante único:** Guilherme Costa

**Projeto:** Sistema Inteligente para Priorização de Chamados de Manutenção

## Preparação

Execute `python app.py` e abra `http://127.0.0.1:5000`, ou utilize a [demonstração pública verificada](https://guilhermedevsoftware.github.io/priorizacao-chamados-manutencao/). Na página estática, confira a indicação de modo demonstração. Explique no início que os chamados e os rótulos foram criados para fins acadêmicos.

## Apresentação de aproximadamente cinco minutos

1. **Problema e objetivo:** equipes pequenas precisam identificar cedo riscos e interrupções essenciais. O programa sugere uma classe e a pessoa responsável decide a ordem de atendimento.
2. **Dados:** mostre o CSV com 120 chamados fictícios, as cinco entradas, a justificativa dos rótulos e as famílias de cenários. Explique que descrições e IDs não foram usados para classificar.
3. **Treino:** mostre o notebook com 96 registros para treino e 24 para teste, separados por família com semente 42. A profundidade foi escolhida apenas no treino e resultou em 6.
4. **Resultados:** mostre sensibilidade, precisão e acurácia de 100% no teste fictício. Compare com a maioria do treino: 100% de sensibilidade e 58,33% de precisão/acurácia. Explique que a maioria prevê todos como prioritários e que o teste pequeno não comprova desempenho real.
5. **Demonstração do formulário:** execute os casos abaixo e leia o resumo. Diga que as expectativas são definidas pela política didática e que as evidências medidas ficam no relatório de testes.
6. **Encerramento:** mostre a API, o JSON compartilhado e o teste de paridade. Apresente a limitação da base sintética e a proposta de parceria para coleta e validação supervisionadas.

## Casos para apresentar

| Caso fictício | Risco | Essencial interrompido | Pessoas | Dias | Recorrente | Comportamento esperado |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Maçaneta frouxa em sala desocupada, sem risco de aprisionamento | 0 | 0 | 0 | 2 | 0 | Normal |
| Falta de água na escola, impedindo a higiene | 0 | 1 | 200 | 1 | 0 | Prioritário |
| Fiação exposta em área de pouca circulação | 1 | 0 | 1 | 0 | 0 | Prioritário |
| Formulário com pessoas afetadas em branco | 0 | 0 | desconhecido | 0 | 0 | Mensagem de validação; nenhuma previsão |

Não preencha automaticamente desconhecidos como zero. Se mostrar a extração generativa, explique que só funciona no Flask com credencial configurada, que exige confirmação e que nesta entrega foi validada com respostas simuladas, sem chamada real.

## Respostas a perguntas prováveis

**Por que houve 100% no teste?** A base é pequena e fictícia, com rótulos derivados de regras explícitas. O modelo reproduziu esses padrões nos 24 exemplos reservados; o resultado não prova generalização real.

**Por que separar famílias?** Variações do mesmo problema poderiam ficar quase idênticas em treino e teste e aumentar artificialmente a avaliação. Todas as quatro variações de uma família permanecem no mesmo conjunto.

**O texto é classificado pela IA generativa?** A classe final sempre vem da árvore. A integração opcional só sugere campos, que precisam ser confirmados.

**Quem decide o atendimento?** O responsável pela manutenção. A classe não substitui inspeção, procedimentos de emergência ou julgamento técnico.
