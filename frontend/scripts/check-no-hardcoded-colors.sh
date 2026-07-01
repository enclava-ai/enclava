#!/usr/bin/env bash
set -euo pipefail

target="${1:-src}"

if [[ ! -e "$target" ]]; then
  echo "Color guardrail target does not exist: $target" >&2
  exit 2
fi

pattern='empire-|enclava-|text-glow|enclava-glow|#[0-9A-Fa-f]{3,8}|\b(red|green|blue|yellow|orange|purple|pink|indigo|cyan|teal|emerald|amber|slate|gray|zinc|neutral|stone|rose|violet|sky|lime)-[0-9]{2,3}\b|rgba?\(|hsla?\([[:space:]]*[0-9]'

if matches=$(
  rg -n --color never \
    --glob '*.{ts,tsx,css}' \
    --glob '!app/api/**' \
    --glob '!src/app/api/**' \
    --glob '!frontend/src/app/api/**' \
    --glob '!lib/proxy-auth.ts' \
    --glob '!src/lib/proxy-auth.ts' \
    --glob '!frontend/src/lib/proxy-auth.ts' \
    "$pattern" \
    "$target"
); then
  echo "Disallowed hardcoded colors or legacy palette names found:" >&2
  echo "$matches" >&2
  exit 1
fi

echo "No disallowed hardcoded colors found in $target."
