"""
build_prompts_ref.py — Gera references/prompts-ia.md a partir de rules.py.

Executa esse script sempre que adicionar/alterar regras com needs_ai_review=True
para manter o arquivo de referência sincronizado.

Uso:
    python build_prompts_ref.py [--output /path/to/prompts-ia.md]
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rules import ai_review_rules


HEADER = """# Prompts da IA por regra

Este arquivo é referência para o Claude da sessão quando processar a fila de revisão IA (`ai-queue_*.jsonl`).

Para CADA bloco na fila:
1. Leia o `content` do arquivo
2. Para cada regra em `rules`, aplique o prompt correspondente abaixo
3. Para cada ocorrência analisada, gere uma linha JSON em `ai-results_*.jsonl`:

```json
{"file": "src/x.prw", "rule": "CA2050", "results": [
  {"line": 47, "is_violation": true, "confidence": "high", "reasoning": "...", "suggested_fix": "...", "matched_text": "trecho disparador"}
]}
```

**Campos da resposta:**
- `line`: número da linha (1-indexed)
- `is_violation`: `true` se for violação real, `false` se for falso positivo
- `confidence`: `"high"`, `"medium"` ou `"low"`
- `reasoning`: explicação curta (1-2 frases) do raciocínio
- `suggested_fix`: sugestão de correção (opcional, quando `is_violation=true`)
- `matched_text`: trecho de código que dispara a regra (opcional)

**Importante:** se a IA encontrar issues NOVAS que o regex não pegou (em modo `all-files`), inclua na lista de `results` com `is_violation=true`. O `consolidate.py` vai detectá-las pela combinação `(file, rule, line)` que não existia no relatório regex.

---

"""


def build_markdown() -> str:
    out = [HEADER]
    for r in ai_review_rules():
        out.append(f"## {r.code} — {r.title}\n\n")
        out.append(f"**Severidade:** {r.severity}  \n")
        out.append(f"**Categoria:** {r.category}  \n\n")
        out.append(r.ai_prompt or "_(sem prompt definido)_")
        out.append("\n\n---\n\n")
    return "".join(out)


def main():
    parser = argparse.ArgumentParser()
    default_out = Path(__file__).parent.parent / "references" / "prompts-ia.md"
    parser.add_argument("--output", default=str(default_out))
    args = parser.parse_args()

    content = build_markdown()
    Path(args.output).write_text(content, encoding="utf-8")
    print(f"[OK] Gerado: {args.output} ({len(content)} chars, {len(ai_review_rules())} regras)")


if __name__ == "__main__":
    main()
