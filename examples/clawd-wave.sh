#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'Użycie: bash %s "Tekst do wyświetlenia"\n' "$0" >&2
  exit 2
fi

: "${PIPCLOCK_TOKEN:?Ustaw i wyeksportuj PIPCLOCK_TOKEN przed uruchomieniem skryptu}"
base_url="${PIPCLOCK_URL:-http://maclock.internal.krosno.cloud:8765}"

curl -q --silent --show-error --fail-with-body --get \
  "${base_url%/}/api/react" \
  -H "Authorization: Bearer $PIPCLOCK_TOKEN" \
  --data-urlencode 'mood=wave' \
  --data-urlencode "text=$1" \
  --data-urlencode 'duration=8'
printf '\n'
