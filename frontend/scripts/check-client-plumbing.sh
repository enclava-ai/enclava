#!/usr/bin/env bash
set -euo pipefail

target="src"
include_dialogs=false

for arg in "$@"; do
  case "$arg" in
    --include-dialogs)
      include_dialogs=true
      ;;
    *)
      target="$arg"
      ;;
  esac
done

if [[ ! -e "$target" ]]; then
  echo "Client plumbing guardrail target does not exist: $target" >&2
  exit 2
fi

nav_pattern='window\.location\.href[[:space:]]*=[[:space:]]*["'\'']/|location\.(assign|replace)\([[:space:]]*["'\'']/|window\.open\([[:space:]]*["'\'']/'
fetch_pattern='\bfetch[[:space:]]*\('
dialog_pattern='(^|[^.[:alnum:]_$])(window\.)?(confirm|alert|prompt)[[:space:]]*\('

failures=0

if matches=$(rg -n --color never --glob '*.{ts,tsx}' "$nav_pattern" "$target"); then
  echo "Disallowed internal browser navigation found:" >&2
  echo "$matches" >&2
  failures=1
fi

if matches=$(
  rg -n --color never \
    --glob '*.{ts,tsx}' \
    --glob '!app/api/**' \
    --glob '!src/app/api/**' \
    --glob '!frontend/src/app/api/**' \
    --glob '!lib/api-client.ts' \
    --glob '!src/lib/api-client.ts' \
    --glob '!frontend/src/lib/api-client.ts' \
    --glob '!lib/token-manager.ts' \
    --glob '!src/lib/token-manager.ts' \
    --glob '!frontend/src/lib/token-manager.ts' \
    --glob '!lib/proxy-auth.ts' \
    --glob '!src/lib/proxy-auth.ts' \
    --glob '!frontend/src/lib/proxy-auth.ts' \
    --glob '!lib/file-download.ts' \
    --glob '!src/lib/file-download.ts' \
    --glob '!frontend/src/lib/file-download.ts' \
    --glob '!lib/url-utils.ts' \
    --glob '!src/lib/url-utils.ts' \
    --glob '!frontend/src/lib/url-utils.ts' \
    --glob '!components/extract/IntegrationGuide.tsx' \
    --glob '!src/components/extract/IntegrationGuide.tsx' \
    --glob '!frontend/src/components/extract/IntegrationGuide.tsx' \
    "$fetch_pattern" \
    "$target"
); then
  echo "Disallowed client fetch usage found:" >&2
  echo "$matches" >&2
  failures=1
fi

if [[ "$include_dialogs" == "true" ]]; then
  if matches=$(rg -n --color never --glob '*.{ts,tsx}' "$dialog_pattern" "$target"); then
    echo "Native dialog usage found:" >&2
    echo "$matches" >&2
    failures=1
  fi
fi

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi

echo "No disallowed client plumbing patterns found in $target."
