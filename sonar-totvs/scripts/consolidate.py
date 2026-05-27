"""
consolidate.py — Consolida resultados da revisão IA (Claude da sessão) com o
relatório gerado pelo analyzer.py.

O Claude da sessão lê `ai-queue_*.jsonl`, analisa cada bloco aplicando os
prompts das regras complexas, e grava as respostas em `ai-results_*.jsonl`.

Este script:
1. Lê o relatório JSON original (gerado pelo analyzer)
2. Lê os resultados da IA (ai-results_*.jsonl)
3. Para cada issue marcada como 'pending':
   - Se a IA confirmou: mantém com ai_status='confirmed' + reasoning
   - Se a IA descartou: marca ai_status='rejected' + reasoning (não conta no score)
4. Adiciona issues NOVAS que a IA encontrou (que regex não pegou)
5. Recalcula scores
6. Gera relatório HTML final e novo JSON

Uso:
    python consolidate.py \\
      --project /path/projeto \\
      --skill-dir /path/skill \\
      --analysis-json sonar_totvs/relatorio_20260527_152030.json \\
      --ai-results sonar_totvs/ai-results_20260527_152030.jsonl
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rules import RULES_BY_CODE, BUG, CODE_SMELL, VULNERABILIDADE
import report


WEIGHTS = {BUG: 3, VULNERABILIDADE: 5, CODE_SMELL: 1}


def calculate_scores(issues: list[dict], total_files: int) -> dict:
    """Calcula scores considerando apenas issues que NÃO foram rejeitadas pela IA."""
    if total_files == 0:
        return {"simple": 100.0, "weighted": 100.0, "files_clean": 0, "files_total": 0}

    active = [i for i in issues if i.get("ai_status") != "rejected"]
    files_with_issues = {i["file"] for i in active}
    files_clean = total_files - len(files_with_issues)
    simple = (files_clean / total_files) * 100

    weighted_sum = sum(WEIGHTS[i["severity"]] for i in active)
    penalty = min(100.0, (weighted_sum / total_files) * 2)
    weighted = max(0.0, 100.0 - penalty)

    return {
        "simple": round(simple, 2),
        "weighted": round(weighted, 2),
        "files_clean": files_clean,
        "files_total": total_files,
    }


def build_fix_prompt_from_dict(iss: dict) -> str:
    """Gera prompt de correção a partir do dict de issue."""
    rule = RULES_BY_CODE.get(iss["rule_code"])
    if not rule:
        return ""
    extra_context = ""
    if iss.get("ai_reasoning"):
        extra_context = f"\n\n**Análise da IA:** {iss['ai_reasoning']}"
    return f"""Corrija a violação da regra Sonar TOTVS **{iss['rule_code']} ({rule.title})** no arquivo `{iss['file']}`, linha {iss['line']}.

**Descrição da regra:**
{rule.description}

**Como corrigir (orientação do Sonar):**
{rule.how_to_fix}

**Trecho atual do código:**
```advpl
{iss['snippet']}
```

**Texto que disparou a regra:** `{iss['matched_text']}`{extra_context}

Refatore aplicando a orientação acima. Preserve a lógica original, o estilo e a indentação do arquivo."""


def main():
    parser = argparse.ArgumentParser(description="Sonar TOTVS — Consolidator")
    parser.add_argument("--project", required=True)
    parser.add_argument("--skill-dir", required=True)
    parser.add_argument("--analysis-json", required=True, help="Caminho do relatorio_*.json gerado pelo analyzer")
    parser.add_argument("--ai-results", required=True, help="Caminho do ai-results_*.jsonl com respostas da IA")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    project_root = Path(args.project).resolve()
    skill_dir = Path(args.skill_dir).resolve()
    analysis_path = Path(args.analysis_json).resolve()
    ai_results_path = Path(args.ai_results).resolve()

    if not analysis_path.is_file():
        print(f"ERRO: análise não encontrada: {analysis_path}", file=sys.stderr)
        sys.exit(2)
    if not ai_results_path.is_file():
        print(f"ERRO: resultados IA não encontrados: {ai_results_path}", file=sys.stderr)
        sys.exit(2)

    output_dir = Path(args.output_dir) if args.output_dir else (project_root / "sonar_totvs")
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Carrega análise base
    with open(analysis_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    issues = payload["issues"]
    files_total = payload["files_analyzed"]

    # 2. Carrega resultados da IA
    # Formato esperado por linha do jsonl:
    # {"file": "src/x.prw", "rule": "CA2050", "results": [
    #    {"line": 47, "is_violation": true, "confidence": "high",
    #     "reasoning": "...", "suggested_fix": "...", "matched_text": "..."},
    #    ...
    # ]}
    ai_verdicts: dict[tuple[str, str, int], dict] = {}
    new_issues_from_ai: list[dict] = []
    ai_lines_processed = 0

    with open(ai_results_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"[WARN] Linha {line_num} de ai-results inválida: {e}", file=sys.stderr)
                continue
            ai_lines_processed += 1
            file_rel = rec.get("file")
            rule_code = rec.get("rule")
            results = rec.get("results", [])
            for r in results:
                line_no = r.get("line")
                key = (file_rel, rule_code, line_no)
                ai_verdicts[key] = r

    print(f"[INFO] {ai_lines_processed} entradas processadas da fila IA")
    print(f"[INFO] {len(ai_verdicts)} vereditos individuais da IA")

    # 3. Aplica vereditos nas issues pending
    confirmed = 0
    rejected = 0
    no_verdict = 0
    for iss in issues:
        if iss.get("ai_status") != "pending":
            continue
        key = (iss["file"], iss["rule_code"], iss["line"])
        verdict = ai_verdicts.get(key)
        if verdict is None:
            # IA não opinou: por segurança mantém como pending (será exibido com ressalva)
            no_verdict += 1
            continue
        if verdict.get("is_violation"):
            iss["ai_status"] = "confirmed"
            iss["origin"] = "regex+ai"
            confirmed += 1
        else:
            iss["ai_status"] = "rejected"
            rejected += 1
        iss["ai_reasoning"] = verdict.get("reasoning", "")
        iss["ai_confidence"] = verdict.get("confidence", "medium")

    print(f"[INFO] Vereditos aplicados: {confirmed} confirmados, {rejected} rejeitados, {no_verdict} sem veredito")

    # 4. Issues NOVAS da IA (que regex não pegou — só em modo all-files)
    # Identificadas por keys de ai_verdicts que não existem em issues
    existing_keys = {(i["file"], i["rule_code"], i["line"]) for i in issues}
    for (file_rel, rule_code, line_no), verdict in ai_verdicts.items():
        if (file_rel, rule_code, line_no) in existing_keys:
            continue
        if not verdict.get("is_violation"):
            continue
        rule = RULES_BY_CODE.get(rule_code)
        if not rule:
            continue
        new_issue = {
            "rule_code": rule_code,
            "rule_title": rule.title,
            "severity": rule.severity,
            "category": rule.category,
            "file": file_rel,
            "line": line_no,
            "column": 1,
            "snippet": verdict.get("matched_text", "(linha apontada pela IA)"),
            "matched_text": verdict.get("matched_text", ""),
            "origin": "ai",
            "ai_status": "confirmed",
            "ai_reasoning": verdict.get("reasoning", ""),
            "ai_confidence": verdict.get("confidence", "medium"),
        }
        issues.append(new_issue)
        new_issues_from_ai.append(new_issue)

    if new_issues_from_ai:
        print(f"[INFO] {len(new_issues_from_ai)} issues NOVAS detectadas pela IA (não pegas pelo regex)")

    # 5. Recalcula scores
    scores = calculate_scores(issues, files_total)
    print(f"[INFO] Scores recalculados: simples {scores['simple']}%, ponderado {scores['weighted']}%")

    # Conta por severidade (só issues ativas — pending ou confirmed)
    counts = {BUG: 0, CODE_SMELL: 0, VULNERABILIDADE: 0}
    active_issues = [i for i in issues if i.get("ai_status") != "rejected"]
    for iss in active_issues:
        counts[iss["severity"]] += 1

    # 6. Atualiza fix_prompt agora com reasoning da IA quando disponível
    for iss in issues:
        iss["fix_prompt"] = build_fix_prompt_from_dict(iss)

    # 7. Salva resultado consolidado
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_html = output_dir / f"relatorio_consolidado_{timestamp}.html"
    out_json = output_dir / f"relatorio_consolidado_{timestamp}.json"

    consolidated_payload = {
        "kind": "analysis_consolidated",
        "timestamp": timestamp,
        "project": payload["project"],
        "files_analyzed": files_total,
        "scores": scores,
        "counts": {
            "bugs": counts[BUG],
            "code_smells": counts[CODE_SMELL],
            "vulnerabilidades": counts[VULNERABILIDADE],
            "total": len(active_issues),
            "rejected_by_ai": rejected,
            "new_from_ai": len(new_issues_from_ai),
        },
        "ai_review": {
            **payload.get("ai_review", {}),
            "confirmed": confirmed,
            "rejected": rejected,
            "no_verdict": no_verdict,
            "new_from_ai": len(new_issues_from_ai),
        },
        "issues": issues,
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(consolidated_payload, f, ensure_ascii=False, indent=2)

    html = report.render_report(consolidated_payload, skill_dir)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n[OK] Relatório consolidado HTML: {out_html}")
    print(f"[OK] JSON consolidado: {out_json}")


if __name__ == "__main__":
    main()
