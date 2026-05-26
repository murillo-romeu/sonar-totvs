# Sonar TOTVS — Claude Skill

Skill para o **Claude** que analisa projetos **TOTVS Protheus** (AdvPL/TLPP) contra o catálogo oficial de regras do SonarQube TOTVS, gera relatório HTML visual com **Bugs**, **Code Smells** e **Vulnerabilidades**, e aplica correções automáticas configuráveis.

![Severidade](https://img.shields.io/badge/regras-60+-blue) ![Linguagem](https://img.shields.io/badge/AdvPL-TLPP-orange) ![Licença](https://img.shields.io/badge/license-MIT-green)

---

## ✨ O que faz

- 📊 **Análise estática** de fontes `.prw` e `.tlpp` contra 60+ regras do Sonar TOTVS
- 📈 **Score duplo de conformidade**: simples (% arquivos limpos) + ponderado (Bug=3, Vulnerab.=5, Smell=1)
- 🎨 **Relatório HTML interativo**: filtros por severidade, busca, drill-down por regra
- 🤖 **Prompts prontos pro Claude** em cada issue não corrigível automaticamente — basta copiar e colar
- 🔧 **Correção automática** configurável: 3 perfis (`safe`, `medium`, `all`) ou lista customizada
- 📅 Cada execução gera arquivo datado em `sonar_totvs/` no projeto

## 📦 Instalação

### Via Claude Code (recomendado)

```bash
/plugin marketplace add murillo-romeu/sonar-totvs
/plugin install sonar-totvs@murillo-romeu
```

### Via upload manual no Claude.ai

1. Baixe o `sonar-totvs.skill` da [última release](../../releases/latest)
2. No Claude.ai vá em **Settings → Capabilities → Skills**
3. Clique em **Upload skill** e selecione o arquivo

### Via clone (Claude Code local)

```bash
git clone https://github.com/SEU-USUARIO/sonar-totvs.git ~/.claude/skills/sonar-totvs
```

## 🚀 Como usar

Com a skill instalada e o projeto aberto no Claude, basta pedir:

```
/sonar-analyze
```

ou em linguagem natural:

> "Analisa esse projeto com o sonar da TOTVS"
> "Roda análise de qualidade nos fontes"
> "Verifica conformidade AdvPL"

Pra aplicar correções automáticas:

```
/sonar-fix
```

> "Corrige as issues do sonar"
> "Aplica os fixes seguros"

A skill vai perguntar quais regras corrigir (perfis `safe`/`medium`/`all` ou lista customizada) e gerar o relatório em `sonar_totvs/correcao_YYYYMMDD_HHMMSS.html`.

## 🧪 Exemplo de saída

A skill gera dois tipos de relatório, ambos HTML responsivos com dark mode:

| Modo | Arquivo | Conteúdo |
|------|---------|----------|
| Análise | `sonar_totvs/relatorio_YYYYMMDD_HHMMSS.html` | Score, contagem por categoria, lista de issues com prompts |
| Correção | `sonar_totvs/correcao_YYYYMMDD_HHMMSS.html` | Score antes/depois, fixes aplicados, issues remanescentes |

Cada issue traz:
- Severidade e código da regra
- Snippet do código com a linha destacada
- Descrição da regra e orientação de fix
- **Botão "Copiar"** com prompt pronto pra colar no Claude

## 📋 Regras cobertas

A skill detecta padrões para **~25 regras** (das ~60 do catálogo oficial), incluindo:

**Bugs**
- `CA1000` — Driver ISAM (MSCREATE, DBUSEAREA, CRIATRAB...)
- `CA1002` — APIs de interface em transação (MsgAlert, Help, Pergunte...)
- `CA1003` — GetMv/ExistBlock em loop
- `CA2000` a `CA2014` — Manipulação direta de metadados (SM0, SIX, SX1, SX3, SX7, SX9...)
- `CA2016` — Funções de log sem I18N
- `CA2019` — APIs binárias (FRead, FWrite, FOpen...)
- `CA2021` — Tabela SE5 descontinuada
- `CA2022`/`CA2023` — StaticCall, PTInternal

**Code Smells**
- `CA1004` — ConOut/OutErr/OutStd (deve usar FWLogMsg)
- `CA1006` — AllUsers (descontinuado, usar FWSFAllUsers)
- `CA2015` — Sobrescrita de FormCommit
- `CA2052` — Senha exposta em código
- `CA3001` — Include em uppercase
- `CA4000` — Uso de IIF (preferir If/Else)

**Vulnerabilidades**
- `CA2050` — SQL Injection por concatenação

## 🔧 Correção automática

| Código | Estratégia | Perfil |
|--------|-----------|--------|
| `CA3001` | Lowercase no nome do include | `safe` |
| `CA4000` | IIF → If/Else (quando standalone) | `safe` |
| `CA1004` | Comenta linha + TODO sugerindo FWLogMsg | `medium` |
| `CA1006` | `AllUsers()` → `FWSFAllUsers()` | `medium` |
| `CA2020` | Adiciona TODO ao lado | `all` |
| `CA2021` | Comenta linha + TODO | `all` |
| `CA2052` | Comenta + TODO sugerindo GetMV | `all` |

As demais ~35 regras detectadas geram **prompt no relatório** pra correção manual via Claude.

## ⚠️ Limitações conhecidas

- **Detecção por regex**, não por parser AST oficial — podem ocorrer falsos positivos
- Regras que dependem de contexto profundo (estar dentro de `Begin Transaction` ou loop) usam heurística
- A skill **não substitui** a análise oficial do TOTVS Code Analysis em pipeline de CI/CD; é um complemento local pra feedback rápido

## 📚 Referências

- [Catálogo oficial das regras](https://sonar-rules.engpro.totvs.com.br/rules) (rede interna TOTVS)
- [TOTVS Code Analysis](https://hub.docker.com/r/totvsengpro/advpl-tlpp-code-analyzer) — análise oficial em container
- [Guia de boas práticas AdvPL](https://tdn.totvs.com)

## 🤝 Contribuições

PRs são bem-vindos! Áreas com maior necessidade:

- Mais padrões de detecção para reduzir falsos negativos
- Fixes automáticos adicionais (CA1000, CA2050, CA2002...)
- Testes em projetos Protheus reais variados

## 📄 Licença

[MIT](LICENSE)

---

Criado com 💙 para a comunidade Protheus/AdvPL.
