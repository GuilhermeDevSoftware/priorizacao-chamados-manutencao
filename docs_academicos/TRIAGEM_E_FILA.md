# Triagem e fila de manutenção

O Flask serve o formulário, a API e a fila. O SQLite grava os chamados e o histórico de alterações. As fotos ficam em `instance/uploads/` com nome gerado no servidor. A demonstração pública mostra exemplos fictícios e permite testar os filtros, a ordem da fila e as explicações.

## Executar no Windows

Extraia o pacote e abra o CMD na pasta que contém `app.py`. Use Python 3.12.

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Abra [http://127.0.0.1:5000](http://127.0.0.1:5000). Para instalar apenas as dependências da interface e da API, use `requirements-web.txt`. Em Linux ou macOS, os executáveis do ambiente virtual ficam em `.venv/bin/`.

Para atualizar uma instalação anterior, encerre o Flask e faça uma cópia da pasta `instance`. Extraia o novo pacote em outra pasta e copie `instance` para ela. Se você criou um `.env`, copie-o localmente e confira os campos novos em `.env.example`. O Flask atualiza o banco ao iniciar. Os IDs, as fotos, as equipes e os status anteriores são mantidos. A prioridade binária anterior é convertida para Não prioritário ou Prioritário e identificada como classificação anterior, sem inventar justificativa ou confiança.

## Como a prioridade é decidida

| Prioridade | Significado | Cor |
| --- | --- | --- |
| Prioritário | Perigo grave, dano imediato ou interrupção crítica de serviço essencial | Vermelho |
| Intermediário | Impacto importante ou localizado que requer atendimento em prazo razoável | Amarelo/laranja |
| Não prioritário | Rotina, prevenção ou defeito pequeno sem impacto relevante identificado | Verde |

Com `OPENAI_API_KEY` no `.env` do Flask, a triagem analisa descrição, respostas e foto opcional com o modelo indicado em `OPENAI_MODEL`. A resposta estruturada inclui proposta, evidências e justificativa. O sistema aplica regras de segurança a eventos críticos no contexto descrito, combina as evidências e indica contradições ou incertezas para revisão. Um sinal de risco grave não é rebaixado por uma resposta negativa. A resposta positiva à pergunta **Existe risco iminente à vida?** em uma descrição de reparo rotineiro pede confirmação humana.

O modo local é identificado como **Análise local**. Ele usa condições textuais contextuais limitadas e as respostas complementares. Por exemplo, distingue um relato ativo de gás da negação explícita desse evento. Não analisa pixels nem oferece a cobertura semântica do provedor. Expressões fora da cobertura podem exigir revisão. A confiança da IA é qualitativa quando disponível e não representa uma probabilidade calibrada. O alerta em caso crítico orienta seguir os procedimentos de emergência da instituição.

Clique em **Analisar chamado** para ver a justificativa e em **Salvar chamado** para persistir o registro. O servidor decide a classificação e registra sua origem. O arquivo acadêmico da árvore binária, o notebook e a rota `/api/prever` permanecem disponíveis para reprodução dos experimentos. A árvore não decide a fila atual.

## Fila e alterações autorizadas

A visão Pendentes inclui chamados abertos e em atendimento. A ordem é prioridade vigente decrescente, abertura crescente e, em caso de empate de horário, ID crescente. A visão Histórico reúne os concluídos. Os contadores mostram todos os pendentes por prioridade, mesmo quando há filtros. Cadastro e alteração atualizam a lista de imediato. A página visível também consulta o servidor periodicamente.

Para habilitar edição administrativa, defina `PRIORIZA_ADMIN_TOKEN` e `PRIORIZA_ADMIN_NOME` no `.env` e reinicie o Flask. Gere uma credencial com:

```bat
.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Insira a credencial no painel apenas para atualizar um chamado. Cada alteração efetiva grava data, responsável definido no servidor, valores anteriores e novos e motivo, quando fornecido. Alterar a prioridade exige motivo. A classificação sugerida originalmente continua visível. A configuração oferece uma credencial de manutenção por instalação. Para identificar vários responsáveis em uma instalação institucional, use controle de identidade individual na infraestrutura.

## API e hospedagem

| Rota | Uso |
| --- | --- |
| `POST /api/classificar` | Envia `multipart/form-data` com `dados` em JSON (descrição e cinco respostas) e `foto` opcional. Retorna prioridade, justificativa, fatores, confiança e revisão. |
| `POST /api/chamados` | Cadastra e persiste um chamado após confirmação do formulário. O comprovante da análise pode ser reaproveitado para a mesma descrição, campos e foto. |
| `GET /api/chamados?visao=pendentes` | Fila e contagens. Aceita `visao=historico` ou `todos` e os filtros `equipe`, `prioridade` e `status`. Os valores de prioridade são `0`, `1` e `2`. |
| `GET /api/chamados/<id>` | Detalhe com classificação e histórico de alterações. |
| `PATCH /api/chamados/<id>` | Atualiza `equipe_confirmada`, `status` ou `prioridade_atual` com `Authorization: Bearer …`. Envie `motivo` para mudança de prioridade. |
| `GET /api/chamados/<id>/foto` | Entrega a foto validada do chamado. |

No banco e na API, o status de conclusão continua sendo `Resolvido` por compatibilidade. A interface exibe **Concluído**. A antiga rota `/api/analisar` continua fazendo sugestões de equipe e preenchimento. Fotos JPEG, PNG e WebP são verificadas pelo servidor, normalizadas e têm metadados removidos. Mantenha o banco e os uploads fora do repositório.

A imagem Docker serve a interface e a API Flask pelo Waitress. Ela executa como usuário sem privilégios e usa um volume persistente:

```bash
docker build -t prioriza .
docker volume create prioriza-dados
docker run --rm --name prioriza --env-file .env -e PRIORIZA_DATA_DIR=/var/lib/prioriza -p 127.0.0.1:5000:5000 -v prioriza-dados:/var/lib/prioriza prioriza
```

Crie o `.env` a partir de `.env.example` antes do comando acima. Para usar a aplicação em servidor, monte armazenamento persistente em `PRIORIZA_DATA_DIR` e encaminhe o acesso ao Flask por HTTPS. A interface e a API devem ser servidas pelo mesmo endereço. Restrinja o acesso à rede institucional ou a um serviço de autenticação quando houver dados reais. O GitHub Pages e o Sites servem a demonstração estática. Nenhum deles hospeda o SQLite deste projeto.

## Como validar

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

O teste usa bancos temporários e simula o provedor sem chamadas externas. A suíte distingue fumaça elétrica, perda de rede localizada, teclado defeituoso, vazamento de gás confirmado, negação de gás e a contradição de risco em reparo pequeno. Também verifica empate de abertura, migração, atualização protegida, alteração de ordem e consulta ao histórico. Use os exemplos fictícios da interface para apresentar a triagem.

Os scripts Playwright e as evidências gravadas das entregas anteriores testam o fluxo binário. Para reproduzi-los, use a versão correspondente em sua tag. Para validar a triagem e a fila atuais, use a suíte acima.
