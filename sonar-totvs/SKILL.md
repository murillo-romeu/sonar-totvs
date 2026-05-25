---
name: sonar-totvs
description: Analisa projetos TOTVS Protheus (AdvPL/TLPP) contra as regras do SonarQube da TOTVS, gera relatório HTML visual com Bugs, Code Smells e Vulnerabilidades, e pode aplicar correções automáticas. Use SEMPRE que o usuário mencionar "análise sonar", "sonar totvs", "qualidade de código protheus", "verificar AdvPL", "verificar TLPP", "analisar fontes Protheus", pedir para checar conformidade de código TOTVS, ou usar os comandos /sonar-analyze, /sonar-fix, /sonar-totvs. Também acione quando o usuário pedir para "corrigir issues do sonar", "rodar análise de qualidade nos fontes", ou qualquer pedido que envolva validar/corrigir código `.prw` ou `.tlpp` contra padrões corporativos. A saída é uma pasta `sonar_totvs/` no projeto contendo relatório HTML datado com scores de conformidade, prompts prontos para correção via Claude, e (se solicitado) correções aplicadas direto nos arquivos.
---

# Sonar TOTVS — Análise de Qualidade AdvPL/TLPP

Analisa projetos Protheus contra o catálogo oficial de regras Sonar da TOTVS, gerando relatório HTML rico e (opcionalmente) aplicando correções automáticas.

## Quando usar esta skill

Use SEMPRE que o usuário pedir qualquer um dos seguintes:

- Análise/verificação de qualidade em projeto Protheus, AdvPL ou TLPP
- Comandos `/sonar-analyze`, `/sonar-fix`, `/sonar-totvs`
- "Rodar sonar no projeto", "checar conformidade", "verificar fontes Protheus"
- Aplicar correções automáticas em issues do Sonar TOTVS
- Gerar relatório de qualidade/score de fontes `.prw` ou `.tlpp`

## O que a skill faz

**Dois modos de operação:**

1. **Análise** (default): varre `.prw` e `.tlpp` do projeto, detecta violações das ~60 regras catalogadas, gera relatório HTML visual em `sonar_totvs/relatorio_YYYYMMDD_HHMMSS.html` com:
   - Score de conformidade simples (% arquivos limpos) e ponderado (Bug=3, Vulnerabilidade=5, Smell=1)
   - Cards de Bugs / Code Smells / Vulnerabilidades
   - Tabela filtrável de issues (severidade, regra, arquivo)
   - Para cada issue: snippet de código + descrição da regra + **prompt pronto pra colar no Claude** corrigindo aquela ocorrência

2. **Correção** (opcional): aplica fixes automáticos diretamente nos arquivos (sem backup — assume branch dedicada), gera `sonar_totvs/correcao_YYYYMMDD_HHMMSS.html` mostrando antes/depois, score delta, e issues que não puderam ser corrigidas (com prompts).

## Workflow obrigatório

### Passo 1 — Identificar o diretório do projeto

O projeto-alvo é o **diretório de trabalho atual onde o Claude Code foi invocado**, não o diretório da skill. Use `pwd` para descobrir:

```bash
PROJECT_DIR=$(pwd)
echo "Analisando projeto em: $PROJECT_DIR"
```

Se o usuário passar um caminho explícito ("analisa o projeto em /home/dev/protheus-integration"), use esse.

### Passo 2 — Confirmar parâmetros com o usuário

Pergunte (ou infira do pedido) antes de rodar:

1. **Modo**: análise apenas, ou análise + correção automática?
2. **Se correção**: quais regras corrigir automaticamente? Apresente as 7 regras com fix automático disponível (ver lista em `references/regras-fix-automatico.md`) e deixe ele escolher: todas, só triviais (CA3001, CA4000), ou subset específico.
3. **Escopo**: projeto inteiro ou subpasta específica?

Se o pedido for direto e explícito (ex: "/sonar-analyze"), pode rodar com defaults: modo análise, projeto inteiro.

### Passo 3 — Rodar o analisador

```bash
python /caminho/para/sonar-totvs/scripts/analyzer.py \
  --project "$PROJECT_DIR" \
  --skill-dir /caminho/para/sonar-totvs
```

Para correção automática:

```bash
python /caminho/para/sonar-totvs/scripts/fixer.py \
  --project "$PROJECT_DIR" \
  --skill-dir /caminho/para/sonar-totvs \
  --rules CA3001,CA4000,CA1004
```

O `--rules` aceita lista separada por vírgula, ou `all` para todas as auto-corrigíveis, ou `safe` para só as triviais (CA3001, CA4000).

### Passo 4 — Apresentar resultado

Após o script rodar:

1. Mostre ao usuário o caminho do relatório gerado (`{projeto}/sonar_totvs/relatorio_*.html`)
2. Resuma em 3-5 linhas: total de issues, distribuição por categoria, score atual
3. Destaque as 3-5 issues mais críticas (Vulnerabilidades primeiro, depois Bugs)
4. Sugira próximos passos: "quer que eu aplique correções automáticas?" ou "quer que eu corrija manualmente alguma issue específica?"

## Estrutura da skill

```
sonar-totvs/
├── SKILL.md (este arquivo)
├── scripts/
│   ├── analyzer.py       — varredura + detecção + geração do relatório
│   ├── fixer.py          — aplica correções automáticas
│   ├── rules.py          — catálogo de regras com padrões regex
│   └── report.py         — geração do HTML
├── references/
│   ├── regras-sonar.md            — catálogo completo (consultar para detalhes)
│   └── regras-fix-automatico.md   — quais regras têm fix automático
└── assets/
    └── report_template.html       — template do dashboard
```

## Detalhes importantes

### Regras com fix automático disponível

Apenas estas 7 regras têm fix automático seguro implementado:

| Código | Regra | Fix |
|--------|-------|-----|
| CA3001 | Include em lower case | Converte `#include "FILE.CH"` → `#include "file.ch"` |
| CA4000 | Não utilização de IIF | Converte `IIF(c, a, b)` standalone para `If/Else/EndIf` |
| CA1004 | API de Console | Comenta `ConOut/OutErr/OutStd` e sugere `FWLogMsg` (deixa TODO) |
| CA1006 | AllUsers descontinuada | Troca `AllUsers()` → `FWSFAllUsers()` |
| CA2021 | Tabela SE5 descontinuada | Comenta linha e marca TODO |
| CA2020 | Função descontinuada | Adiciona comentário TODO ao lado |
| CA2052 | Senha exposta | Substitui valor literal por `GetMV()` e marca TODO |

Todas as outras (~53 regras) **só geram prompt para o Claude resolver** — ficam no relatório como issues sem fix automático.

### Detecção das regras

A detecção usa **regex sobre código-fonte** porque não temos o parser ANTLR oficial da TOTVS. Isso significa:

- Falsos positivos podem ocorrer (ex: ocorrência dentro de comentário ou string)
- O analisador filtra comentários `//` e blocos `/* */` antes de aplicar os padrões
- Strings (entre `"..."` e `'...'`) também são mascaradas, exceto para detecção de SQL Inject (CA2050) que precisa do conteúdo das strings

### Score de conformidade

**Score simples:** `(arquivos sem issues / total de arquivos) * 100`

**Score ponderado:** `100 - min(100, (sum(issues * peso) / total_arquivos) * 2)`, com pesos:
- Bug = 3
- Vulnerabilidade = 5
- Code Smell = 1

Ambos são exibidos no topo do relatório com cor (verde > 80, amarelo 50-80, vermelho < 50).

### Prompts no relatório

Cada issue no relatório HTML traz um bloco "Prompt para correção" com texto pronto tipo:

> Corrija a violação `CA2050 (Sql Inject)` no arquivo `src/cli/orders.prw` linha 47. O código atual é:
> ```
> dbUseArea(.T., "TOPCONN", TcGenQry(,,"SELECT * FROM SE1 WHERE E1_NUM = " + cNum), "TRB", .T., .T.)
> ```
> Refatore usando `FWPreparedStatement` ou `TcGenQry2` com parameter binding. Mantenha a lógica original e o estilo do arquivo.

Esse prompt pode ser copiado e colado em outra conversa com o Claude pra resolução individual.

## Tratamento de erros

- **Projeto sem fontes `.prw`/`.tlpp`**: avisar o usuário e abortar antes de gerar relatório vazio
- **Permissão de escrita negada** em `sonar_totvs/`: avisar e sugerir verificar permissões
- **Arquivo com encoding inválido** (não-UTF8 / não-Windows-1252): pular, logar warning, continuar

## Referências

- Catálogo completo das regras: `references/regras-sonar.md`
- Lista de fixes automáticos disponíveis: `references/regras-fix-automatico.md`
- Site oficial das regras (interno TOTVS): https://sonar-rules.engpro.totvs.com.br/rules
