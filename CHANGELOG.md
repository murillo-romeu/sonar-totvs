# Changelog

Todas as mudanças notáveis deste projeto serão documentadas aqui.
O formato é baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/),
e este projeto adere ao [Semantic Versioning](https://semver.org/lang/pt-BR/).

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
