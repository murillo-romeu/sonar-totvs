# Contribuindo

Obrigado pelo interesse em contribuir! 🎉

## Estrutura do projeto

```
sonar-totvs/
├── SKILL.md                 # Manifesto da skill (Claude lê isso primeiro)
├── scripts/
│   ├── analyzer.py          # Varredura + detecção
│   ├── fixer.py             # Aplicação de fixes
│   ├── rules.py             # Catálogo de regras com regex
│   └── report.py            # Geração do HTML
├── references/
│   ├── regras-sonar.md      # Catálogo oficial (60+ regras)
│   └── regras-fix-automatico.md
└── assets/                  # (futuro) templates e fontes
```

## Como rodar localmente

```bash
# Clone o repo
git clone https://github.com/SEU-USUARIO/sonar-totvs.git
cd sonar-totvs

# Rode contra um projeto Protheus qualquer
python sonar-totvs/scripts/analyzer.py \
  --project /caminho/para/projeto-protheus \
  --skill-dir ./sonar-totvs

# Ou rode os fixes
python sonar-totvs/scripts/fixer.py \
  --project /caminho/para/projeto-protheus \
  --skill-dir ./sonar-totvs \
  --rules safe
```

## Como adicionar uma nova regra

1. Abra `sonar-totvs/scripts/rules.py`
2. Adicione um novo objeto `Rule(...)` na lista `RULES` com:
   - `code`: código oficial (ex: `"CA2027"`)
   - `title`: título da regra
   - `severity`: `BUG`, `CODE_SMELL` ou `VULNERABILIDADE`
   - `category`: categoria (Performance, Security, etc)
   - `description`: explicação curta
   - `how_to_fix`: orientação de correção
   - `patterns`: lista de regex pré-compiladas
3. Crie um arquivo de teste em `.prw` com a violação esperada
4. Rode o analyzer e confirme que a regra é detectada
5. Opcional: implemente um fix automático em `fixer.py` e adicione ao `FIX_FUNCTIONS`

## Como adicionar um fix automático

1. Implemente uma função `fix_caXXXX(source: str) -> tuple[str, int]` em `fixer.py`
2. Registre em `FIX_FUNCTIONS`
3. Adicione ao perfil apropriado (`safe`, `medium` ou `all`) em `FIX_GROUPS`
4. Atualize a tabela em `references/regras-fix-automatico.md`
5. Atualize a tabela no `README.md`

## Padrões de código

- Python 3.10+ (usa `tuple[int, int]`, walrus operator, etc)
- Sem dependências externas (`pip install` zero) — só stdlib
- Comentários e mensagens de log em português (consistente com o público alvo)
- Strings de erro/log em inglês são OK pra logs técnicos

## Pull requests

- Crie uma branch a partir de `main` com nome descritivo (`feat/ca2025-detection`)
- Faça um commit por mudança lógica
- Descreva no PR: o que mudou, por que, como testar
- Inclua um caso de teste (.prw) que demonstre a mudança
