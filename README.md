# PINTURA

Painel de controle operacional do processo de pintura, construído com FastAPI, SQLAlchemy 2.0, Alembic, Jinja2 e MySQL.

## O que foi criado

- Estrutura modular em `app/` com separação de rotas, models e serviços.
- Dashboard operacional nível 2 com filtro por data/turno, central de alertas, prioridade automática por módulo, pendências por turno e ocorrências do dia entre ED, Pressão, Tensão e Temperatura.
- Seção `ED` operacional com contexto de lançamento, carregamento de itens compatíveis, salvamento em rascunho, conclusão, histórico e visualização detalhada.
- Seção `Pressão dos Filtros ED` operacional com 24 filtros, detecção automática de alarmes, rascunho, conclusão, histórico e detalhe.
- Seção `Tensão dos Retificadores ED` operacional com 29 zonas por lançamento, múltiplos lançamentos no dia por `turno + modelo`, validação automática da faixa `80V a 400V`, rascunho, conclusão, histórico e detalhe.
- Seção `Temperatura Forno ED` operacional com 12 zonas térmicas, cálculo automático de faixa válida, rascunho, conclusão, histórico e detalhe.
- Páginas placeholder para `Poder de penetração`, `Espessura ED`, `Aspecto` e `Rugosidade`.
- CRUD server-side para `responsaveis`, `modelos`, `setores`, `turnos` e `itens_ed`.
- Configuração de conexão MySQL por variáveis de ambiente.
- Alembic configurado com migration inicial, seed dos itens fixos da ED e migrations incrementais dos módulos operacionais.
- Migrations incrementais dos módulos operacionais adicionadas até `20260413_0005_tensao_retificadores.py`.
- CSS centralizado com visual limpo, industrial e profissional.
- Testes em `tests/test_app.py` cobrindo dashboard operacional, fluxos de ED, Pressão, Tensão, Temperatura e precedência de rotas.

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
6. Acesse `/dashboard`, `/ed`, `/pressao-filtros-ed`, `/tensao-retificadores-ed` e `/temperatura-forno-ed` para usar a visão consolidada e os módulos operacionais já implementados.

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
- Use a seção `Alertas do dia` para abrir rapidamente ocorrências de `ED`, `Pressão dos Filtros ED`, `Tensão dos Retificadores ED` e `Temperatura Forno ED`.
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

## Fluxo de Tensão dos Retificadores ED

- Abra `http://127.0.0.1:8000/tensao-retificadores-ed`.
- Preencha `data`, `turno`, `modelo` e `responsável`.
- Clique em `Carregar formulário` para exibir as 29 zonas dos retificadores.
- Informe a tensão de cada zona; o sistema destaca automaticamente leituras abaixo de `80V` ou acima de `400V`.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para finalizar em modo leitura.
- O sistema aceita múltiplos lançamentos no mesmo dia, desde que a combinação `data + turno + modelo` seja única.
- Consulte `http://127.0.0.1:8000/tensao-retificadores-ed/historico` para filtrar por período, turno, modelo, status e ocorrências fora do padrão.

## Fluxo de Temperatura Forno ED

- Abra `http://127.0.0.1:8000/temperatura-forno-ed`.
- Preencha `data` e `responsável`.
- Clique em `Carregar formulário` para exibir as 12 zonas térmicas do forno.
- Informe a temperatura de cada zona; o sistema calcula automaticamente a faixa válida e destaca zonas fora do padrão.
- Use `Salvar rascunho` para continuar depois ou `Concluir lançamento` para finalizar em modo leitura.
- Consulte `http://127.0.0.1:8000/temperatura-forno-ed/historico` para filtrar por período, status e ocorrências fora do padrão.

## Observação de escopo

- `ED` já está operacional nesta etapa.
- `Pressão dos Filtros ED` já está operacional nesta etapa.
- `Tensão dos Retificadores ED` já está operacional nesta etapa.
- `Temperatura Forno ED` já está operacional nesta etapa.
- As demais seções (`Poder de Penetração`, `Espessura`, `Aspecto` e `Rugosidade`) continuam como placeholder estruturado.

## Próxima etapa já preparada

- Repetir o padrão operacional da ED e de Pressão dos Filtros ED para as próximas seções reais.
- Adicionar histórico analítico mais rico, filtros avançados e rastreabilidade temporal.
- Relacionar `itens_ed` com entidades de referência de forma mais rígida, se necessário.
- Incluir autenticação, permissões e regras operacionais específicas sem reestruturar a base.
