# PINTURA

Painel de controle operacional do processo de pintura, construído com FastAPI, SQLAlchemy 2.0, Alembic, Jinja2 e MySQL.

## O que foi criado

- Estrutura modular em `app/` com separação de rotas, models e serviços.
- Dashboard operacional nível 2 com filtro por data/turno, central de alertas, prioridade automática por módulo, pendências por turno e ocorrências do dia entre ED, Espessura, Poder de Penetração, Rugosidade, Pressão, Tensão, Temperatura e Aspecto.
- Seção `ED` operacional com contexto de lançamento, carregamento de itens compatíveis, salvamento em rascunho, conclusão, histórico e visualização detalhada.
- Seção `Pressão dos Filtros ED` operacional com 24 filtros, detecção automática de alarmes, rascunho, conclusão, histórico e detalhe.
- Seção `Espessura ED` operacional com 38 pontos de medição, rascunho, conclusão, rastreabilidade por modelo/CIS, histórico e detalhe técnico.
- Seção `Poder de Penetração` operacional com coleta semanal, 30 pontos, cálculo automático de aprovados/reprovados, menor valor e `% de aprovação`, com rascunho, conclusão, histórico e detalhe técnico.
- Seção `Rugosidade` operacional com matriz por `data + sequência`, modelos fixos `521`, `226`, `551`, `598` e `291`, cálculo automático de fora do padrão por limite `14 µin`, rascunho, conclusão, histórico e detalhe técnico.
- Seção `Tensão dos Retificadores ED` operacional com 29 zonas por lançamento, múltiplos lançamentos no dia por `turno + modelo`, validação automática da faixa `80V a 400V`, rascunho, conclusão, histórico e detalhe.
- Seção `Temperatura Forno ED` operacional com 12 zonas térmicas, cálculo automático de faixa válida, rascunho, conclusão, histórico e detalhe.
- Seção `Aspecto` operacional com entrada dinâmica de até 10 carrocerias por lote, registro rápido de anomalias visuais, histórico e detalhe consolidado.
- Não há placeholders restantes entre os módulos principais do ciclo operacional.
- CRUD server-side para `responsaveis`, `modelos`, `setores`, `turnos` e `itens_ed`.
- Configuração de conexão MySQL por variáveis de ambiente.
- Alembic configurado com migration inicial, seed dos itens fixos da ED e migrations incrementais dos módulos operacionais.
- Migrations incrementais dos módulos operacionais adicionadas até `20260413_0009_rugosidade.py`.
- CSS centralizado com visual limpo, industrial e profissional.
- Testes em `tests/test_app.py` cobrindo dashboard operacional, fluxos de ED, Espessura, Pressão, Tensão, Temperatura, Aspecto e precedência de rotas.

## Estrutura principal

```text
app/
  main.py
  config.py
  db.py
  models/
  routes/
  services/
  static/css/
  static/js/
  templates/
alembic/
tests/
requirements.txt
README.md
```

## Configuração rápida

1. Copie `.env.example` para `.env` e ajuste usuário/senha do MySQL.
2. Crie o banco `pintura` no MySQL.
3. Instale as dependências.
4. Rode todas as migrations.
5. Inicie a aplicação.
6. Acesse `/dashboard`, `/ed`, `/espessura-ed`, `/poder-penetracao`, `/rugosidade`, `/pressao-filtros-ed`, `/tensao-retificadores-ed`, `/temperatura-forno-ed` e `/aspecto` para usar a visão consolidada e os módulos operacionais já implementados.

## Comandos

```powershell
Copy-Item .env.example .env
C:/Users/se15218/AppData/Local/Programs/Python/Python314/python.exe -m pip install -r requirements.txt
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS pintura CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
C:/Users/se15218/AppData/Local/Programs/Python/Python314/python.exe -m alembic upgrade head
C:/Users/se15218/AppData/Local/Programs/Python/Python314/python.exe -m uvicorn app.main:app --reload
C:/Users/se15218/AppData/Local/Programs/Python/Python314/python.exe -m pytest tests/test_app.py -q
```

## Fluxo da ED

- Abra `http://127.0.0.1:8000/ed`.
- Preencha `data`, `tipo do dia`, `setor`, `turno` e `responsável`.
- Clique em `Carregar itens` para trazer os itens fixos aplicáveis do contexto.
- Informe `valor coletado` e `observação` por item.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para fechar em modo somente leitura.
- Consulte `http://127.0.0.1:8000/ed/historico` para filtrar e abrir lançamentos anteriores.

## Dashboard Operacional do Dia

- Abra `http://127.0.0.1:8000/dashboard`.
- Filtre por `data` e, se necessário, por `turno`.
- Use a seção `Alertas do dia` para abrir rapidamente ocorrências de `ED`, `Pressão dos Filtros ED`, `Tensão dos Retificadores ED`, `Temperatura Forno ED`, `Poder de Penetração`, `Rugosidade` e `Aspecto`.
- Use os cards operacionais para acompanhar também as frentes `Espessura ED`, `Poder de Penetração` e `Rugosidade`, com visibilidade de lançamentos, rascunhos, pontos preenchidos e modelos fora do padrão.
- Acompanhe no topo os indicadores de `Módulos OK`, `Módulos com problema`, `Total de alertas` e `Pendências`.
- Os cards dos módulos aplicam prioridade automática:
  - `Crítico`: existe desvio no dia.
  - `Atenção`: existe rascunho pendente.
  - `OK`: lançamento concluído sem desvio.
  - `Não iniciado`: não há lançamento.
- Use a ação rápida inteligente de cada card:
  - `Ver problema`
  - `Continuar`
  - `Visualizar`
  - `Iniciar`
- Consulte a `Matriz de fechamento` para identificar pendências por turno e a seção `Ocorrências do dia` para abrir direto o evento relevante.

## Fluxo de Pressão dos Filtros ED

- Abra `http://127.0.0.1:8000/pressao-filtros-ed`.
- Preencha `data`, `turno` e `responsável`.
- Clique em `Carregar formulário` para exibir os 24 filtros.
- Informe a pressão de cada filtro; o sistema marca alarme automaticamente quando o valor for maior que `1.0`.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para finalizar em modo leitura.
- Consulte `http://127.0.0.1:8000/pressao-filtros-ed/historico` para filtrar por período, turno, status e alarmes.

## Fluxo de Espessura ED

- Abra `http://127.0.0.1:8000/espessura-ed`.
- Preencha `data`, `turno`, `modelo`, `responsável` e, se disponível, o `CIS`.
- Clique em `Carregar pontos` para abrir o grid técnico com os `38` pontos de medição.
- Informe os valores de espessura em `µm`; nesta fase o sistema destaca apenas valores muito fora do padrão futuro, sem aplicar faixa rígida de bloqueio.
- Use `Salvar rascunho` para manter medições parciais ou `Concluir lançamento` para bloquear a edição.
- Consulte `http://127.0.0.1:8000/espessura-ed/historico` para filtrar por `data`, `turno`, `modelo` e `status` e abrir o detalhe técnico.

## Fluxo de Poder de Penetração

- Abra `http://127.0.0.1:8000/poder-penetracao`.
- Preencha `data`, `semana`, `modelo`, `responsável` e, se disponível, `CIS`, `velocidade` e `tipo`.
- Clique em `Carregar pontos` para abrir o grid técnico com os `30` pontos do ensaio semanal.
- Informe os valores medidos; o sistema classifica automaticamente cada ponto como `Aprovado` quando `>= 7.9` ou `Reprovado` quando abaixo desse valor.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para bloquear a edição.
- Consulte `http://127.0.0.1:8000/poder-penetracao/historico` para filtrar por `semana`, `data`, `modelo` e `status` e abrir o detalhe técnico com `% de aprovação`.

## Fluxo de Rugosidade

- Abra `http://127.0.0.1:8000/rugosidade`.
- Preencha `data`, `sequência` e `responsável`.
- Clique em `Carregar matriz` para abrir a matriz fixa dos modelos `521`, `226`, `551`, `598` e `291`.
- Informe os valores de rugosidade por modelo; o sistema classifica automaticamente como `OK` quando `<= 14 µin` e `Fora do padrão` quando acima desse limite.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para bloquear a edição.
- Consulte `http://127.0.0.1:8000/rugosidade/historico` para filtrar por `data`, `sequência`, `status` e opcionalmente só lançamentos com desvio.

## Fluxo de Tensão dos Retificadores ED

- Abra `http://127.0.0.1:8000/tensao-retificadores-ed`.
- Preencha `data`, `turno`, `modelo` e `responsável`.
- Clique em `Carregar formulário` para exibir as 29 zonas dos retificadores.
- Informe a tensão de cada zona; o sistema destaca automaticamente leituras abaixo de `80V` ou acima de `400V`.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para finalizar em modo leitura.
- O sistema aceita múltiplos lançamentos no mesmo dia, desde que a combinação `data + turno + modelo` seja única.
- Consulte `http://127.0.0.1:8000/tensao-retificadores-ed/historico` para filtrar por período, turno, modelo, status e ocorrências fora do padrão.

## Fluxo de Aspecto

- Abra `http://127.0.0.1:8000/aspecto`.
- Preencha `data`, `turno`, `modelo` e `responsável`.
- Use `Adicionar carroceria` para montar rapidamente o lote com até `10` carrocerias por envio.
- Em cada bloco informe `CIS`, `código da posição`, `local`, `anomalia`, `lado`, `geração` e `quantidade`.
- Clique em `Salvar registros` para gravar o lote completo direto como lançamento concluído.
- Consulte `http://127.0.0.1:8000/aspecto/historico` para filtrar por `data`, `turno` e `modelo` e abrir o detalhe do lote.

## Fluxo de Temperatura Forno ED

- Abra `http://127.0.0.1:8000/temperatura-forno-ed`.
- Preencha `data` e `responsável`.
- Clique em `Carregar formulário` para exibir as 12 zonas térmicas do forno.
- Informe a temperatura de cada zona; o sistema calcula automaticamente a faixa válida e destaca zonas fora do padrão.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para finalizar em modo leitura.
- Consulte `http://127.0.0.1:8000/temperatura-forno-ed/historico` para filtrar por período, status e ocorrências fora do padrão.

## Observação de escopo

- `ED` já está operacional nesta etapa.
- `Espessura ED` já está operacional nesta etapa.
- `Pressão dos Filtros ED` já está operacional nesta etapa.
- `Tensão dos Retificadores ED` já está operacional nesta etapa.
- `Temperatura Forno ED` já está operacional nesta etapa.
- `Aspecto` já está operacional nesta etapa.
- `Poder de Penetração` já está operacional nesta etapa.
- `Rugosidade` já está operacional nesta etapa.

## Próxima etapa já preparada

- Repetir o padrão operacional da ED e de Pressão dos Filtros ED para as próximas seções reais.
- Adicionar histórico analítico mais rico, filtros avançados e rastreabilidade temporal.
- Relacionar `itens_ed` com entidades de referência de forma mais rígida, se necessário.
- Incluir autenticação, permissões e regras operacionais específicas sem reestruturar a base.
