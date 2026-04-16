# Design System — SaaS App UI
Versão: 1.0.0

## 1. Visão geral

Este design system foi extraído de referências visuais com foco em:
- interfaces SaaS premium e minimalistas
- alta densidade de informação com leitura limpa
- sensação de produto maduro, discreto e confiável
- visual leve, claro, sofisticado e orientado a produtividade

**Não é uma cópia literal da referência.**  
O objetivo aqui é transformar a linguagem visual observada em um sistema consistente, reutilizável e viável para desenvolvimento frontend real.

---

## 2. Tom visual geral

### Personalidade visual
- Clean
- Quiet premium
- Analítico
- Profissional
- Editorial-tech
- Minimalista, mas não frio
- Denso sem parecer poluído

### Sensação que a interface deve transmitir
- organização
- controle
- clareza
- leveza
- sofisticação silenciosa
- produto bem-acabado

### Princípios de composição
1. **Muito espaço em branco útil**  
   O layout respira, mas não desperdiça área.
2. **Hierarquia suave**  
   Pouco contraste agressivo; o peso visual vem da organização.
3. **Contornos discretos**  
   Bordas finas e sombras leves substituem blocos pesados.
4. **Componentes arredondados**  
   Cantos suaves, aparência contemporânea e amigável.
5. **Base neutra com acentos pontuais**  
   A maior parte da interface vive em neutros claros; cor entra como sinal funcional.
6. **Densidade controlada**  
   Ideal para dashboards, CRM, gestão, analytics, backoffice e apps operacionais.

---

## 3. Paleta de cores aproximada

## Estratégia de cor
A referência sugere uma base quase monocromática, com:
- fundo cinza-claro muito suave
- superfícies brancas ou off-white
- texto em grafite
- bordas em cinza claro
- acentos pequenos em preto, verde, rosa/framboesa e âmbar

### Base neutra
- **Canvas**: cinza muito claro, levemente quente
- **Surface**: branco puro ou quase branco
- **Surface alt**: cinza claríssimo para agrupamentos
- **Border**: cinza claro de baixa presença
- **Text primary**: grafite quase preto
- **Text secondary**: cinza médio
- **Text tertiary**: cinza suave

### Acentos funcionais
- **Primary/Ink**: preto suave / grafite profundo
- **Accent**: rosa-framboesa controlado, para highlights analíticos ou CTA secundário
- **Success**: verde dessaturado e claro
- **Warning**: âmbar suave
- **Danger**: vermelho moderado, nunca saturado demais
- **Info**: azul acinzentado

### Uso recomendado
- 75% neutros claros
- 15% neutros médios/escuros
- 10% acentos funcionais

### Regras
- não usar cor vibrante como base da interface
- evitar fundos pesados em grandes áreas
- usar preto/grafite em CTAs primários
- reservar verde para status positivos
- reservar rosa/accent para métricas, foco, seleção ou destaque editorial
- usar vermelho apenas para erro, destruição ou alertas relevantes

---

## 4. Tipografia sugerida

## Família principal
**Inter** como padrão.

Fallback:
`Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`

## Família monoespaçada
Para tabelas técnicas, IDs, números e logs:
`"JetBrains Mono", "SFMono-Regular", ui-monospace, monospace`

## Características tipográficas
- visual neutro e moderno
- excelente legibilidade em UI densa
- funciona bem em métricas, labels, tabelas e formulários
- ideal para layouts SaaS com cara de produto real

## Escala sugerida
- `12px` — labels auxiliares, badge pequeno, meta info
- `13px` — texto utilitário e tabela compacta
- `14px` — base principal de interface
- `16px` — inputs, body confortável, títulos menores
- `18px` — subtítulos
- `20px` — títulos de seção
- `24px` — títulos de página compactos
- `30px` — métricas ou hero interno
- `36px` — números-chave em dashboards

## Pesos sugeridos
- `400` regular
- `500` medium
- `600` semibold
- `700` bold apenas para números-chave e destaque restrito

## Regras de uso
- corpo padrão da interface: `14px / 20px`
- labels de formulário e tabela: `12px` ou `13px`
- títulos de cards: `14px` a `16px`, peso `600`
- títulos de página: `24px`, peso `600`
- métricas principais: `28px` a `36px`, peso `600` ou `700`
- evitar títulos enormes; a referência é compacta e refinada

---

## 5. Espaçamento

## Filosofia
Espaçamento consistente, modular e econômico.

## Escala base
Base de 4px:
- 4
- 8
- 12
- 16
- 20
- 24
- 32
- 40
- 48
- 64
- 80

## Regras práticas
- espaço entre label e input: `6px` a `8px`
- padding interno de input: `10px 12px`
- padding de botão médio: `10px 14px`
- padding de card: `16px` a `20px`
- gap entre cards: `16px`
- gap em grids principais: `20px` a `24px`
- distância entre seções de página: `24px` a `32px`

## Densidade por contexto
### Compacta
Para CRM, tabelas, dashboards operacionais:
- row height menor
- padding horizontal controlado
- tipografia 13–14px

### Confortável
Para detalhes, formulários, configuração:
- padding mais generoso
- maior separação entre blocos
- mais respiro vertical

---

## 6. Border radius

## Direção visual
Cantos arredondados suaves, mas sem exagero.

## Escala recomendada
- `8px` — badges, chips pequenos
- `10px` — inputs compactos
- `12px` — botões padrão, itens de lista
- `16px` — cards
- `20px` — painéis destacados
- `24px` — modais grandes
- `999px` — pill, badge cápsula, toggle

## Regras
- radius pequeno para elementos interativos repetitivos
- radius médio para containers
- radius grande apenas em superfícies principais e modais

---

## 7. Sombras

## Filosofia
Sombras sutis, difusas e limpas.  
Nada pesado, dramático ou “glassmorphism” exagerado.

## Camadas
### Shadow XS
Para inputs, cards sutis e divisões leves

### Shadow SM
Para cards padrão

### Shadow MD
Para dropdowns, popovers e elementos destacados

### Shadow LG
Para modais e overlays

## Regras
- usar sombra sempre combinada com borda clara
- não depender só de sombra para separação
- em superfícies muito claras, manter sombras extremamente suaves

---

## 8. Bordas e divisórias

## Largura
- padrão: `1px`

## Estilo
- sólido
- baixo contraste
- nunca muito escuro

## Uso
- cards
- tabelas
- inputs
- agrupamentos internos
- topbar e sidebar com divisões finas

## Regra
Preferir:
- borda clara + sombra leve  
ao invés de
- borda escura + bloco pesado

---

## 9. Layout

## App shell
Estrutura recomendada:
- sidebar fixa ou semi-fixa à esquerda
- topbar horizontal no conteúdo principal
- área central com cards, métricas, tabelas e painéis
- uso intenso de grid

## Grid
### Desktop
- 12 colunas
- gutter `24px`

### Tablet
- 8 colunas
- gutter `20px`

### Mobile
- 4 colunas
- gutter `16px`

## Larguras
- sidebar expandida: `256px` a `280px`
- sidebar colapsada: `72px` a `88px`
- topbar: `64px` a `72px`
- content max para leitura confortável: `1440px`
- padding lateral desktop: `24px` a `32px`
- padding lateral mobile: `16px`

## Organização de blocos
- métricas no topo
- filtros logo abaixo
- conteúdo analítico/tabela na área principal
- ações contextuais próximas do conteúdo, não soltas no topo sem contexto

---

## 10. Componentes

## 10.1 Botões

### Estilo geral
Botões discretos, compactos, elegantes e arredondados.

### Variações
#### Primary
- fundo grafite/preto suave
- texto branco
- usado para CTA principal

#### Secondary
- fundo branco
- borda clara
- texto escuro
- usado para ações padrão

#### Ghost
- fundo transparente
- hover com preenchimento muito leve
- ideal para topbar, listas e toolbar

#### Soft
- fundo neutro claro
- sem presença excessiva
- ideal para filtros e microações

#### Danger
- fundo vermelho controlado
- uso restrito

### Tamanhos
- `sm`: 32px altura
- `md`: 36px a 40px altura
- `lg`: 44px altura

### Estados
- default
- hover
- active
- focus-visible
- disabled
- loading

### Regras
- botão primário deve aparecer pouco, para manter valor visual
- evitar muitos botões cheios na mesma área
- em telas densas, preferir secondary ou ghost para não “pesar”

---

## 10.2 Inputs

### Estilo geral
Inputs com superfície clara, borda delicada, altura compacta e tipografia legível.

### Características
- fundo branco
- borda cinza clara
- radius médio
- placeholder discreto
- foco com outline sutil ou ring suave

### Alturas
- padrão: `40px`
- compacto: `36px`

### Tipos
- text
- search
- select
- textarea
- combobox
- date range
- inline filter field

### Regras
- evitar sombras fortes no input
- placeholder não deve competir com conteúdo
- labels acima do campo, não dentro como padrão principal
- usar helper text em cinza médio
- usar erro com borda e texto, não só cor

---

## 10.3 Cards

### Estilo geral
Cards claros, arredondados, com borda fina e sombra leve.

### Estrutura
- header opcional
- body
- footer opcional
- divisores internos quando necessário

### Uso
- métricas
- listas
- painéis analíticos
- formulários segmentados
- resumos operacionais

### Variações
- `default`
- `elevated`
- `subtle`
- `interactive`

### Regras
- não usar fundo colorido por padrão
- usar cor de fundo apenas em estados especiais ou widgets métricos
- manter padding consistente

---

## 10.4 Sidebar

### Estilo geral
Sidebar clara, silenciosa, com navegação organizada por grupos.

### Características
- fundo levemente distinto do canvas
- divisões sutis por seção
- ícones simples, lineares
- item ativo com preenchimento discreto
- labels pequenas para categorias
- avatar/conta no rodapé

### Comportamentos
#### Desktop
- expandida por padrão
- grupos visíveis
- largura ~272px

#### Tablet
- pode colapsar para ícones com tooltip

#### Mobile
- vira drawer lateral
- abre por menu/hambúrguer
- overlay escurecido leve

### Regras
- evitar contraste excessivo
- item ativo deve parecer selecionado, não gritante
- agrupamentos claros: Work, Team, Reports, Settings etc.

---

## 10.5 Topbar

### Estilo geral
Topbar limpa, baixa e funcional.

### Elementos típicos
- título contextual ou busca
- ações rápidas
- filtros globais
- avatar/menu
- botões de criação

### Regras
- manter altura contida
- não empilhar muita informação
- busca pode ficar central ou à esquerda
- ações utilitárias preferencialmente à direita

---

## 10.6 Tabelas

### Estilo geral
Tabela refinada, leve, muito legível e compacta.

### Características
- cabeçalho discreto
- texto 13px ou 14px
- divisores leves
- hover suave por linha
- seleção com checkbox
- status com badge pequena
- toolbar contextual ao selecionar linhas

### Regras
- nunca usar grade pesada
- zebra opcional muito sutil
- cabeçalhos não precisam ser escuros
- alinhar números à direita
- textos longos devem truncar com tooltip ou expandir em detalhe

### Densidade
- row height compacta: `40px` a `44px`
- row height confortável: `48px` a `52px`

### Mobile
- priorizar uma destas estratégias:
  1. scroll horizontal controlado com colunas prioritárias
  2. transformação em cards por linha
  3. detalhe expansível por item

---

## 10.7 Modais

### Estilo geral
Modal claro, largo o suficiente, com muito foco no conteúdo.

### Características
- fundo branco/off-white
- radius alto
- sombra maior e limpa
- overlay escuro translúcido
- header simples
- footer com ações alinhadas

### Tamanhos
- `sm`: confirmação
- `md`: formulário curto
- `lg`: configuração avançada
- `xl`: detalhes ricos ou fluxo multi-etapas

### Regras
- evitar modais desnecessariamente estreitos
- manter hierarquia clara
- título, contexto, corpo e ações devem ser bem separados

---

## 10.8 Dropdowns, popovers e context menus

### Estilo geral
Superfícies pequenas, brancas, bem delimitadas e com sombra média.

### Regras
- padding interno 8–12px
- itens com hover leve
- ícone opcional à esquerda
- item destrutivo no fim, em vermelho moderado
- manter agrupamento por seções quando necessário

---

## 10.9 Badges e status

### Estilo geral
Capsulas pequenas, suaves, de baixa saturação.

### Cores
- active → verde suave
- new → azul suave ou neutro frio
- vip / highlight → âmbar suave
- non-targeted / neutral → cinza
- danger → vermelho claro com texto mais escuro

### Regras
- nunca muito vibrantes
- usar texto curto
- padding pequeno
- não competir com o conteúdo principal

---

## 11. Iconografia

## Estilo
- linear
- fino a médio
- simples
- consistente
- sem excesso de detalhes

## Regras
- tamanho comum: `16px`, `18px`, `20px`
- botões redondos utilitários podem usar `16px`
- navegação lateral usa `16px` a `18px`

---

## 12. Interações e estados

## Hover
- mudança sutil de fundo
- leve aumento de contraste
- sem animações exageradas

## Focus
- `focus-visible` claro e acessível
- usar ring suave em vez de brilho excessivo

## Active
- redução pequena de brilho ou leve escurecimento

## Disabled
- opacidade reduzida
- cursor apropriado
- manter legibilidade

## Motion
- rápida e discreta
- `120ms` a `220ms`
- easing suave

### Evitar
- bounce
- overshoot agressivo
- animações “brinquedo”

---

## 13. Regras de layout por breakpoint

## Desktop ≥ 1280px
- sidebar expandida
- dashboards com múltiplas colunas
- tabelas completas
- filtros em linha
- cards métricos em faixa superior

## Tablet 768px–1279px
- sidebar colapsável
- grids de 2 colunas para conteúdo
- filtros podem quebrar em duas linhas
- tabelas com menos colunas visíveis

## Mobile < 768px
- sidebar vira drawer
- topbar mais compacta
- conteúdo em coluna única
- métricas empilhadas
- cards e formulários ocupam largura total
- tabelas viram cards ou scroll horizontal controlado
- ações destrutivas e primárias devem ficar bem separadas

---

## 14. Comportamento mobile

## Objetivo
No mobile, a interface deve continuar premium e organizada, sem parecer “desktop espremido”.

## Regras mobile
- padding lateral: `16px`
- topbar: `56px` a `60px`
- botões principais com altura mínima de `40px`
- campos full width
- usar stacks verticais em vez de mini grids apertados
- reduzir colunas de tabela para 2–3 essenciais
- menus contextuais viram bottom sheet quando fizer mais sentido
- modais complexos podem virar tela cheia
- filtros avançados em drawer ou sheet

---

## 15. Acessibilidade

## Contraste
- texto principal com contraste forte sobre fundo claro
- texto secundário ainda precisa permanecer legível
- badges muito suaves devem manter contraste mínimo adequado

## Tamanho mínimo
- alvo de toque ideal: `40px`
- preferível `44px` em mobile

## Focus visible
- obrigatório em todos os controles interativos

## Semântica
- usar botões reais para ações
- labels associados a inputs
- tabela com semântica correta quando for tabela de fato
- aria-expanded, aria-selected e aria-current quando aplicável

---

## 16. Regras de implementação frontend

## CSS / Tokens
- basear tudo em design tokens
- usar tokens semânticos além dos tokens primitivos
- preferir escala consistente a valores isolados

## Estrutura de temas
Recomendado:
- `primitives`
- `semantic`
- `component`

## Boas práticas
- separar tokens de cor base e cor semântica
- definir estados hover/active/focus em todos os componentes
- manter paddings e radii sistemáticos
- não hardcodar cores de status em componentes sem passar por tokens

---

## 17. Resumo operacional do estilo

Se este design system fosse descrito em uma frase:

**“Um sistema SaaS claro, refinado e silenciosamente premium, com base neutra, alta legibilidade, densidade inteligente e acentos funcionais discretos.”**

---

## 18. Checklist de consistência visual

Antes de aprovar uma tela, verificar:
- a tela respira sem parecer vazia?
- há hierarquia clara entre título, métrica, conteúdo e ação?
- as bordas estão sutis o suficiente?
- os botões primários estão sendo usados com moderação?
- a tabela está legível sem grade pesada?
- o mobile parece pensado, e não apenas adaptado?
- os acentos de cor estão servindo função real?
- o produto parece um software real e maduro?

---

## 19. Componentes prioritários para construir primeiro

1. AppShell
2. Sidebar
3. Topbar
4. Button
5. Input
6. Select
7. SearchField
8. Card
9. MetricCard
10. Badge
11. Table
12. DropdownMenu
13. Modal
14. Tabs
15. EmptyState
16. Pagination
17. Toolbar contextual
18. Drawer mobile

---

## 20. Observação final

A referência aponta para um ecossistema visual muito bom para:
- CRM
- analytics
- ERP leve
- backoffice
- gestão operacional
- produto B2B
- apps de produtividade e fluxo interno

Ao implementar, o maior cuidado deve ser:
**preservar a leveza e a maturidade visual sem cair em excesso de branco vazio nem em UI sem contraste.**