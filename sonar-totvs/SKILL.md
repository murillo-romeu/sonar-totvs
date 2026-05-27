---
name: sonar-totvs
description: Analisa projetos TOTVS Protheus (AdvPL/TLPP) contra as regras do SonarQube da TOTVS, gera relatório HTML visual com Bugs, Code Smells e Vulnerabilidades, e pode aplicar correções automáticas. Use SEMPRE que o usuário mencionar "análise sonar", "sonar totvs", "qualidade de código protheus", "verificar AdvPL", "verificar TLPP", "analisar fontes Protheus", pedir para checar conformidade de código TOTVS, ou usar os comandos /sonar-analyze, /sonar-fix, /sonar-totvs. Também acione quando o usuário pedir para "corrigir issues do sonar", "rodar análise de qualidade nos fontes", ou qualquer pedido que envolva validar/corrigir código `.prw` ou `.tlpp` contra padrões corporativos. A análise tem duas fases: regex (rápida, para regras triviais) + IA semântica opcional (Claude da sessão revisa regras complexas como SQL Inject e transações). A saída é uma pasta `sonar_totvs/` no projeto contendo relatório HTML datado com scores de conformidade e prompts prontos para correção via Claude.
---

# Sonar TOTVS — Análise de Qualidade AdvPL/TLPP

Analisa projetos Protheus contra o catálogo oficial de regras Sonar da TOTVS, gerando relatório HTML rico, com revisão semântica opcional pela IA da própria sessão.

## Quando usar esta skill

Use SEMPRE que o usuário pedir qualquer um dos seguintes:

- Análise/verificação de qualidade em projeto Protheus, AdvPL ou TLPP
- Comandos `/sonar-analyze`, `/sonar-fix`, `/sonar-totvs`
- "Rodar sonar no projeto", "checar conformidade", "verificar fontes Protheus"
- Aplicar correções automáticas em issues do Sonar TOTVS
- Gerar relatório de qualidade/score de fontes `.prw` ou `.tlpp`

## Modos de análise

A skill funciona em **duas fases**:

### Fase 1 — Regex (sempre roda)

Varre todos os `.prw` e `.tlpp`, aplica padrões regex contra as ~30 regras inequívocas (include lowercase, IIF, AllUsers descontinuado, etc). Gera issues imediatamente.

### Fase 2 — Revisão IA (opcional, dispara após Fase 1)

Para as **7 regras complexas** (CA2050 SQL Inject, CA1002 transação, CA1003 loop, CA1000 ISAM, CA2016 I18N, CA2020 deprecated, CA2052 senha), regex apenas pré-filtra candidatos. O Claude da sessão revisa cada candidato com **entendimento semântico**, descartando falsos positivos (ex: SQL com PreparedStatement não é injection) e podendo encontrar issues novas que regex perdeu.

## Workflow obrigatório

### Passo 1 — Identificar o diretório do projeto

```bash
PROJECT_DIR=$(pwd)
echo "Analisando projeto em: $PROJECT_DIR"
```

Se o usuário passar caminho explícito, use esse.

### Passo 2 — Rodar a Fase 1 (regex)

```bash
python /caminho/para/sonar-totvs/scripts/analyzer.py \
  --project "$PROJECT_DIR" \
  --skill-dir /caminho/para/sonar-totvs \
  --ai-mode candidates
```

**Flag `--ai-mode`:**
- `none` — só regex, sem fila de IA
- `candidates` (default) — gera fila de IA só pra arquivos com candidatos pré-filtrados
- `all-files` — todos os arquivos contra todas as regras complexas (mais lento, pode achar issues que regex perdeu)

O analyzer gera:
- `sonar_totvs/relatorio_TIMESTAMP.html` e `.json` — relatório regex
- `sonar_totvs/ai-queue_TIMESTAMP.jsonl` — fila de revisão IA (uma linha por arquivo)

### Passo 3 — Perguntar ao usuário se quer rodar a IA

Após o analyzer rodar, **leia o JSON gerado** e olhe `payload.ai_review`. Se `queue_size > 0`:

> "A análise regex encontrou X issues, sendo Y candidatos a violação em regras complexas (SQL Inject, transação, loop, etc) que precisam de revisão semântica. Quer que eu analise esses Y candidatos agora com IA para descartar falsos positivos? (s/n)"

Se o usuário disser não, vá direto ao Passo 5. Se disser sim:

### Passo 4 — Processar a fila de IA

**Esta é a parte que VOCÊ (Claude da sessão) executa diretamente.**

1. Leia `sonar-totvs/references/prompts-ia.md` para conhecer os prompts de cada regra
2. Leia o arquivo `sonar_totvs/ai-queue_TIMESTAMP.jsonl` (uma linha JSON por arquivo)
3. Para cada linha do jsonl:
   - Cada linha tem `{file, rules, candidates, content}` — note `content` é o source completo do arquivo
   - Para cada `rule` em `rules`, aplique o prompt correspondente do `prompts-ia.md` ao `content`
   - Analise as ocorrências candidatas (e procure novas, se relevante)
   - Gere uma linha de resposta em `sonar_totvs/ai-results_TIMESTAMP.jsonl` com este formato:

```json
{"file": "src/x.prw", "rule": "CA2050", "results": [
  {"line": 47, "is_violation": true, "confidence": "high", "reasoning": "cQuery concatena cNum vindo de parâmetro sem sanitização antes do TcGenQry", "suggested_fix": "Usar FWPreparedStatement com '?'", "matched_text": "TcGenQry(,,\"SELECT ...\"+ cNum)"},
  {"line": 89, "is_violation": false, "confidence": "high", "reasoning": "Query 100% literal, sem variáveis externas"}
]}
```

**Diretrizes ao processar:**
- Trabalhe em batches de 5-10 arquivos por vez para não estourar contexto
- Use `view` para reler o `prompts-ia.md` se precisar revisar critérios
- Cada linha do `ai-results_*.jsonl` cobre UM arquivo + UMA regra (mas pode ter múltiplos `results`)
- Use `create_file` ou `bash_tool` com `>>` para ir gravando incrementalmente

**Atalho recomendado:** se a fila tem muitos arquivos (>50), avise o usuário e ofereça analisar em partes ou só os top-N mais suspeitos.

### Passo 5 — Consolidar o relatório

Após o `ai-results_*.jsonl` estar pronto:

```bash
python /caminho/para/sonar-totvs/scripts/consolidate.py \
  --project "$PROJECT_DIR" \
  --skill-dir /caminho/para/sonar-totvs \
  --analysis-json "$PROJECT_DIR/sonar_totvs/relatorio_TIMESTAMP.json" \
  --ai-results "$PROJECT_DIR/sonar_totvs/ai-results_TIMESTAMP.jsonl"
```

Gera `sonar_totvs/relatorio_consolidado_TIMESTAMP.html` com:
- Scores recalculados (descontando falsos positivos rejeitados pela IA)
- Issues marcadas como `confirmed` (validadas pela IA) ou `rejected` (falso positivo)
- Issues NOVAS encontradas pela IA (quando em modo `all-files`)
- Razão da IA em cada confirmação/rejeição

### Passo 6 — Apresentar resultado ao usuário

1. Mostre o caminho do relatório consolidado
2. Resuma: total de issues confirmadas, quantos falsos positivos a IA descartou, score atual
3. Destaque as 3-5 issues mais críticas (Vulnerabilidades > Bugs)
4. Pergunte: aplicar correções automáticas? Corrigir manualmente alguma issue?

## Para correção automática

Análogo ao analyze, mas roda `fixer.py`:

```bash
python /caminho/para/sonar-totvs/scripts/fixer.py \
  --project "$PROJECT_DIR" \
  --skill-dir /caminho/para/sonar-totvs \
  --rules CA3001,CA4000,CA1004
```

`--rules` aceita: `safe`, `medium`, `all`, ou lista vírgula-separada. Apenas regras com fix automático implementado (ver `references/regras-fix-automatico.md`).

## Estrutura da skill

```
sonar-totvs/
├── SKILL.md (este arquivo)
├── scripts/
│   ├── analyzer.py             — Fase 1 regex + geração da fila IA
│   ├── consolidate.py          — Junta fila IA + resultado regex em relatório final
│   ├── build_prompts_ref.py    — Regenera references/prompts-ia.md a partir de rules.py
│   ├── fixer.py                — Aplica correções automáticas
│   ├── rules.py                — Catálogo de regras (regex + metadados + prompts IA)
│   └── report.py               — Geração do HTML
└── references/
    ├── regras-sonar.md             — Catálogo oficial completo (60+ regras)
    ├── regras-fix-automatico.md    — Quais regras têm fix automático
    └── prompts-ia.md               — Prompts da IA por regra complexa
```

## Detalhes importantes

### Regras regex-only (30 regras)

Detectadas só por regex, sem revisão IA. Inequívocas:
- `CA3001` include uppercase, `CA4000` IIF, `CA1006` AllUsers descontinuado
- `CA2000`–`CA2014` acesso direto a metadados (SM0, SIX, SX1, SX3, etc)
- `CA1004` ConOut, `CA2015` FormCommit, `CA2017`–`CA2023` APIs proibidas
- E mais.

### Regras IA-review (7 regras)

Regex pré-filtra; IA confirma/descarta:
- `CA1000` ISAM (distingue de TOPCONN)
- `CA1002` interface em transação (precisa ver escopo)
- `CA1003` GetMv em loop (precisa ver escopo)
- `CA2016` log sem I18N (precisa entender se é texto p/ usuário)
- `CA2020` função descontinuada (sugere substituta)
- `CA2050` SQL Inject (precisa ver se há sanitização)
- `CA2052` senha exposta (distingue placeholder de credencial real)

### Score de conformidade

**Score simples:** `(arquivos sem issues / total) * 100`

**Score ponderado:** `100 - min(100, (Σ pesos / total_arquivos) * 2)`, pesos: Bug=3, Vulnerab.=5, Smell=1

Issues rejeitadas pela IA **não** entram no score (consideradas falso positivo).

### Tratamento de erros

- **Projeto sem fontes `.prw`/`.tlpp`**: avisar o usuário e abortar
- **Fila IA vazia**: pular o Passo 4, ir direto ao Passo 5 ou ao relatório regex
- **Arquivo com encoding inválido**: pular, logar warning, continuar

## Referências

- `references/regras-sonar.md` — catálogo completo
- `references/regras-fix-automatico.md` — fixes disponíveis
- `references/prompts-ia.md` — prompts pra revisão IA (use no Passo 4)
- Site oficial (interno TOTVS): https://sonar-rules.engpro.totvs.com.br/rules
