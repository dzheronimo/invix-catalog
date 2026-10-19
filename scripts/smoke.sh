#!/usr/bin/env bash
# End-to-end smoke test against a running stack (default http://localhost:8080).
# Exits non-zero on the first failed check with an explicit FAIL message.
set -euo pipefail

BASE="${1:-http://localhost:8080}"
TOKEN="${INTERNAL_TOKEN:-dev-internal-token}"
TMPDIR_SMOKE="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_SMOKE"' EXIT

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

echo "== GET / (catalog page) =="
html="$(curl -fsS "$BASE/")" || fail "catalog page request failed"
echo "$html" | grep -q "Каталог" || fail "page does not contain 'Каталог'"
echo "PASS: page contains 'Каталог'"

echo "== GET /api/products =="
curl -fsS "$BASE/api/products" | grep -q '\[' || fail "product list did not respond with a JSON array"
echo "PASS: product list responds"

echo "== POST /api/products without token is rejected =="
python3 - <<PY
from pathlib import Path
png = bytes.fromhex(
    "89504e470d0a1a0a0000000d494844520000000100000001080600000"
    "01f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
)
Path("$TMPDIR_SMOKE/pixel.png").write_bytes(png)
PY
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/products" \
  -F name=smoke -F file=@"$TMPDIR_SMOKE/pixel.png")"
[ "$code" = "403" ] || fail "anonymous create returned $code, expected 403"
echo "PASS: anonymous create rejected (403)"

echo "== POST /api/products with token =="
resp="$(curl -fsS -X POST "$BASE/api/products" \
  -H "X-Internal-Token: $TOKEN" \
  -F name="smoke-товар" -F file=@"$TMPDIR_SMOKE/pixel.png")" || fail "authorized create failed"
echo "$resp" | grep -q 'smoke-товар' || fail "created product is missing from the response"
product_id="$(echo "$resp" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
echo "PASS: product created (id $product_id)"

echo "== new product appears in the catalog =="
curl -fsS "$BASE/api/products" | grep -q 'smoke-товар' || fail "new product not listed in the catalog"
echo "PASS: listed"

echo "== image is served through the backend =="
curl -fsS "$BASE/api/products/$product_id/image" -o "$TMPDIR_SMOKE/got.png" || fail "image request failed"
cmp -s "$TMPDIR_SMOKE/pixel.png" "$TMPDIR_SMOKE/got.png" || fail "image bytes do not round-trip"
echo "PASS: image bytes round-trip"

echo "SMOKE OK"
