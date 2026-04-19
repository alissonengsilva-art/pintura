# PINTURA

Painel de controle operacional do processo de pintura, construído com FastAPI, SQLAlchemy 2.0, Alembic, Jinja2 e MySQL.

## O que foi criado

- Estrutura modular em `app/` com separação de rotas, models e serviços.
- **Framework genérico de módulos operacionais** com preenchimento independente por setor (PTED e Laboratório).
- Dashboard operacional nível 2 com filtro por data/turno, central de alertas, prioridade automática por módulo, pendências por turno e ocorrências do dia.
- **8 módulos operacionais consolidados** no novo fluxo setorial:
  - `ED` – checklist operacional por contexto.
  - `Pressão dos Filtros` – 24 filtros com alarmes automáticos.
  - `Temperatura Forno` – 12 zonas térmicas.
  - `Tensão dos Retificadores` – 29 zonas por turno/modelo.
  - `Espessura` – 38 pontos de medição por modelo/CIS.
  - `Poder de Penetração` – 30 pontos com aprovação automática semanal.
  - `Rugosidade` – matriz fixa por sequência com limite `14 µin`.
  - `Aspecto` – registro de lote com até 10 carrocerias.
- **Status multinível**: NAO_INICIADO → EM_ANDAMENTO → PARCIAL → CONCLUIDO.
- **Compatibilidade legada**: registros antigos acessíveis via `/modulo/legado/{id}`.
- CRUD server-side para `responsaveis`, `modelos`, `setores`, `turnos` e `itens_ed`.
- Configuração de conexão MySQL por variáveis de ambiente.
- Alembic configurado com migration inicial, seed dos itens fixos da ED e migrations incrementais.
- Migration `20260416_0010_operational_modules.py` com a nova estrutura de módulos operacionais.
- CSS centralizado com visual premium, segmentado e profissional.
- Testes em `tests/test_app.py` cobrindo dashboard operacional, fluxos setoriais e precedência de rotas.

## Estrutura principal

```text
app/
  main.py
  config.py
  db.py
  models/
    operational_module.py    # Novos modelos: OperationalModuleRecord, Sector, Entry
    ...
  routes/
    module_pages.py          # Rotas genéricas para todos os módulos
    ...
  services/
    operational_module_service.py  # Framework de módulos setoriais
    ...
  static/css/
  templates/
    modules/                 # Templates unificados para o novo fluxo
      index.html             # Página principal com controle segmentado
      detail.html            # Detalhe consolidado
      history.html           # Histórico unificado novo + legado
      report.html            # Relatório por setor ou consolidado
      legacy_detail.html     # Visualização de registros antigos
alembic/
tests/
requirements.txt
README.md
```

## Modelo de dados operacional

```text
OperationalModuleRecord (registro mestre)
├── module_code: ed, pressao-filtros-ed, temperatura-forno-ed, ...
├── data_referencia, turno, context_key
├── status_geral: NAO_INICIADO | EM_ANDAMENTO | PARCIAL | CONCLUIDO
└── setores[]
    └── OperationalModuleSectorRecord
        ├── setor_tipo: PTED | LABORATORIO
        ├── responsavel_nome, observacoes_setor
        ├── status_setor: NAO_INICIADO | EM_ANDAMENTO | CONCLUIDO
        └── respostas[]
            └── OperationalModuleSectorEntry
                ├── referencia, ordem
                ├── valor_texto, valor_numero
                ├── observacao, fora_padrao
                └── dados (JSON flexível)
```

## Configuração rápida

1. Copie `.env.example` para `.env` e ajuste usuário/senha do MySQL.
2. Crie o banco `pintura` no MySQL.
3. Instale as dependências.
4. Rode todas as migrations (inclui `20260416_0010_operational_modules`).
5. Inicie a aplicação.
6. Acesse `/dashboard` para visão consolidada ou qualquer módulo direto.

## Comandos

```powershell
Copy-Item .env.example .env
python -m pip install -r requirements.txt
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS pintura CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
python -m pytest tests/test_app.py -q
```

## Novo fluxo operacional

O sistema foi reorganizado em torno do conceito de **Turno Operacional**:

### 1. Turno Atual (`/turno-atual`)
Visão central do turno com todos os 8 módulos:
- Status geral de cada módulo (Não iniciado / Em andamento / Concluído)
- Progresso por setor (PTED / Laboratório)
- Ações rápidas: Iniciar, Continuar ou Visualizar
- Indicação de frequência (Diário / Semanal / Condicional)

### 2. Central do Módulo (`/{slug}`)
Hub com histórico organizado em abas:
- **Concluídos**: registros finalizados com ações Visualizar e Relatório consolidado
- **Em andamento**: registros ativos com ação Continuar
- **Botão "Iniciar ciclo"**: abre modal para configurar contexto e criar novo registro

### 3. Fluxo de Inicialização
1. Clique em **Iniciar ciclo** na central do módulo
2. Configure o contexto no modal (data, turno, modelo, etc.)
3. Sistema cria o registro e redireciona para o checklist vinculado
4. **Contexto travado**: data/turno/modelo ficam em modo somente leitura

### 4. Checklist Vinculado (`/{slug}/registros/{id}/checklist`)
- Contexto exibido em barra readonly (não editável após iniciar)
- Abas PTED / Laboratório para preenchimento independente
- Salvar rascunho ou Concluir setor
- Status evolui: NAO_INICIADO → EM_ANDAMENTO → PARCIAL → CONCLUIDO

### 5. Histórico Geral (`/historico-geral`)
Visão consolidada de todos os turnos:
- Filtros por período, turno, módulo e status
- Agrupamento por dia/turno com módulos expandíveis
- Links diretos para visualização de registros

## Navegação principal

| Página | URL | Descrição |
|--------|-----|-----------|
| Dashboard | `/dashboard` | Visão consolidada com alertas e métricas |
| Turno Atual | `/turno-atual` | Status dos 8 módulos do turno |
| Histórico Geral | `/historico-geral` | Histórico agrupado por turno |
| Pendências | `/pendencias` | Lista de pendências operacionais |
| Central do Módulo | `/{slug}` | Hub com abas Concluídos/Em andamento |

## Rotas disponíveis por módulo

| Rota | Método | Descrição |
|------|--------|-----------|
| `/{slug}` | GET | Central do módulo (hub com abas) |
| `/{slug}/iniciar` | POST | Cria registro e redireciona para checklist |
| `/{slug}/registros/{id}/checklist` | GET | Checklist com contexto travado |
| `/{slug}/setores/{setor}/salvar` | POST | Salva ou conclui setor |
| `/{slug}/registros/{id}` | GET | Detalhe do registro consolidado |
| `/{slug}/registros/{id}/relatorio` | GET | Relatório completo ou por setor |
| `/{slug}/legado/{id}` | GET | Visualização de registros antigos |
| `/{slug}/historico` | GET | Redireciona para central (aba concluídos) |
| `/{slug}/checklist` | GET | Redireciona para central (compatibilidade) |

**Slugs disponíveis**: `ed`, `pressao-filtros-ed`, `temperatura-forno-ed`, `tensao-retificadores-ed`, `espessura-ed`, `poder-penetracao`, `rugosidade`, `aspecto`.

## Dashboard Operacional do Dia

- Abra `http://127.0.0.1:8000/dashboard`.
- Filtre por `data` e, se necessário, por `turno`.
- Use a seção `Alertas do dia` para abrir rapidamente ocorrências com desvio.
- Os cards dos módulos exibem:
  - Status geral e por setor (PTED / Laboratório).
  - Responsáveis de cada setor.
  - Quantidade de desvios detectados.
- Ações rápidas inteligentes:
  - `Iniciar` – quando o contexto ainda não existe.
  - `Continuar` – quando há setor em andamento.
  - `Visualizar` – quando concluído.
- Consulte a `Matriz de fechamento` para identificar pendências por turno.

## Especificidades dos módulos

### ED
- **Contexto**: data + tipo do dia + turno.
- **Itens**: checklist fixo carregado automaticamente por tipo do dia e setor.
- **Validação**: sem regra de faixa rígida (somente registro).

### Pressão dos Filtros
- **Contexto**: data + turno.
- **Itens**: 24 filtros.
- **Validação**: alarme quando pressão > `1.0 bar`.

### Temperatura Forno
- **Contexto**: data.
- **Itens**: 12 zonas térmicas.
- **Validação**: faixa esperada por zona (calculada automaticamente).

### Tensão dos Retificadores
- **Contexto**: data + turno + modelo.
- **Itens**: 29 zonas dos retificadores.
- **Validação**: fora do padrão quando < `80V` ou > `400V`.

### Espessura
- **Contexto**: data + turno + modelo + CIS (opcional).
- **Itens**: 38 pontos de medição.
- **Validação**: destaque para valores muito fora do padrão futuro.

### Poder de Penetração
- **Contexto**: data + semana + modelo + CIS/velocidade/tipo (opcionais).
- **Itens**: 30 pontos do ensaio semanal.
- **Validação**: `Aprovado` se >= `7.9`, `Reprovado` caso contrário.

### Rugosidade
- **Contexto**: data + sequência (1ª, 2ª ou 3ª coleta).
- **Itens**: modelos fixos `521`, `226`, `551`, `598`, `291`.
- **Validação**: `OK` se <= `14 µin`, `Fora do padrão` caso contrário.

### Aspecto
- **Contexto**: data + turno + modelo.
- **Itens**: até 10 carrocerias por lote.
- **Colunas**: CIS, posição, local, anomalia, lado, geração, quantidade.
- **Validação**: cada linha registrada é contada como desvio.

## Status atual

- **Fluxo de Turno Operacional implementado**: visão central em `/turno-atual`.
- **Central de módulo com abas**: Concluídos e Em andamento separados.
- **Modal de inicialização**: contexto definido antes de criar registro.
- **Contexto travado**: não editável após iniciar o ciclo.
- **Frequência por módulo**: diário, semanal ou condicional.
- **Framework setorial**: todos os 8 módulos migrados para o novo padrão.
- **Histórico geral**: visão consolidada agrupada por turno em `/historico-geral`.
- **Compatibilidade legada**: registros antigos acessíveis via `/modulo/legado/{id}`.

## Próxima etapa

- Implementar autenticação e permissões por setor/módulo.
- Adicionar exportação de relatórios em PDF.
- Evoluir dashboard com gráficos de tendência e comparativos.
- Implementar notificações para módulos pendentes do turno.
