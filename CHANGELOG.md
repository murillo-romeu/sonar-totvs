# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.
O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

## [1.1.0] — 2026-05-27

### Adicionado
- **Revisão IA semântica** para 7 regras complexas onde regex sofre de falsos positivos por falta de contexto: `CA2050` (SQL Inject), `CA1002` (interface em transação), `CA1003` (GetMv/ExistBlock em loop), `CA1000` (driver ISAM), `CA2016` (log sem I18N), `CA2020` (função descontinuada), `CA2052` (senha exposta).
- Nova flag `--ai-mode` em `analyzer.py` com 3 opções:
  - `none`: só regex, sem fila de IA
  - `candidates` (padrão): gera fila de IA só pra arquivos com candidatos pré-filtrados
  - `all-files`: todos os arquivos contra todas as regras complexas (mais lento, pode achar issues que regex perdeu)
- Novo script `consolidate.py` que junta o veredito da IA com o resultado do regex, recalcula scores e gera relatório consolidado.
- Novo script `build_prompts_ref.py` que gera `references/prompts-ia.md` automaticamente a partir das definições das regras.
- Novo arquivo `references/prompts-ia.md` com prompts específicos por regra para o Claude da sessão usar na fase de revisão semântica.
- Campos novos em cada issue do relatório: `origin` (regex/ai/regex+ai), `ai_status` (pending/confirmed/rejected), `ai_reasoning`, `ai_confidence`.
- Badges visuais no relatório HTML: 🤖 IA confirmou, 🤖 IA descartou, 🤖 pendente, 🤖 IA detectou.
- Toggle "Mostrar rejeitadas pela IA" no relatório (issues rejeitadas ficam ocultas por padrão).
- Bloco "Análise da IA" em cada card de issue mostrando o raciocínio e nível de confiança (●●● / ●●○ / ●○○).

### Mudanças
- Score ponderado agora **desconta issues rejeitadas pela IA**, refletindo o quadro real de conformidade.
- `SKILL.md` atualizado documentando o novo fluxo de 2 fases (análise → fila IA → consolidação).
- README com seção dedicada à análise em duas fases.

## [1.0.1] — 2026-05-27

### Corrigido
- **CA3001 (Include em lower case)**: regex disparava em TODOS os includes, inclusive nos que já estavam em lowercase. A flag `re.IGNORECASE` aplicada ao regex inteiro fazia `[A-Z]` casar qualquer letra. Corrigido usando inline flag `(?i:include)` que torna case-insensitive apenas a palavra `include`, mantendo o `[A-Z]` do nome do arquivo case-sensitive.
- Título da regra CA3001 ajustado de "Include em lower case" para "Include deve estar em lower case" (mais claro sobre o que é esperado).
- Descrição da CA3001 expandida explicitando que a violação é causada por letras maiúsculas no nome do arquivo.

## [1.0.0] — 2026-05-25

### Adicionado
- Análise estática contra ~25 regras do Sonar TOTVS:
  - **Bugs**: CA1000, CA1002, CA1003, CA2000–CA2014, CA2016–CA2023, CA3002
  - **Code Smells**: CA1001, CA1004, CA1006, CA2015, CA2052, CA3001, CA4000
  - **Vulnerabilidade**: CA2050 (SQL Injection)
- Relatório HTML interativo com:
  - Score simples e score ponderado (Bug=3, Vulnerab.=5, Smell=1)
  - Filtros por severidade e por regra
  - Busca textual
  - Prompts prontos pra correção via Claude (com botão "Copiar")
- Correção automática para 7 regras (CA3001, CA4000, CA1004, CA1006, CA2020, CA2021, CA2052)
- Três perfis de fix: `safe`, `medium`, `all` + lista customizada
- Suporte a múltiplos encodings (UTF-8 e Windows-1252)
- Detecção que mascara comentários e strings para reduzir falsos positivos
