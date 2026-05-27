#!/usr/bin/env bash
# Empacota a skill em um .skill (zip) pronto pra upload manual.
set -euo pipefail

cd "$(dirname "$0")"

SKILL_DIR="sonar-totvs"
OUTPUT="${SKILL_DIR}.skill"

if [ ! -d "$SKILL_DIR" ]; then
  echo "ERRO: pasta '$SKILL_DIR' não encontrada"
  exit 1
fi

# Limpa pycache
find "$SKILL_DIR" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find "$SKILL_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Remove arquivo anterior se existir
rm -f "$OUTPUT"

# Cria o .skill
zip -rq "$OUTPUT" "$SKILL_DIR" -x "*.pyc" -x "*/__pycache__/*" -x "*/.DS_Store"

echo "✅ Skill empacotada: $OUTPUT"
ls -lh "$OUTPUT"
