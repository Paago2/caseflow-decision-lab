#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
DEMO_SUFFIX="${DEMO_SUFFIX:-}"
CASE_ID="demo_case_001${DEMO_SUFFIX}"
REQ_ID="demo-req-001${DEMO_SUFFIX}"

if ! curl -fsS "${BASE_URL}/health" >/dev/null; then
  echo "API is not reachable at ${BASE_URL}. Start it first (e.g., make api)." >&2
  exit 1
fi

echo "== Demo case: ${CASE_ID}"

OCR_RESPONSE="$({
  cat <<'JSON'
{
  "case_id": "__CASE_ID__",
  "document": {
    "filename": "demo_income_note.txt",
    "content_type": "text/plain",
    "content_b64": "U3RhYmxlIHBheXJvbGwgYW5kIGVtcGxveW1lbnQgcmVjb3JkcyBzdXBwb3J0IGluY29tZSB2ZXJpZmljYXRpb24u"
  }
}
JSON
} | sed "s/__CASE_ID__/${CASE_ID}/g" | curl -fsS -X POST "${BASE_URL}/ocr/extract" \
  -H "Content-Type: application/json" \
  -d @-)

DOCUMENT_ID="$(printf '%s' "${OCR_RESPONSE}" | python -c 'import json,sys; print(json.load(sys.stdin)["document_id"])')"

curl -fsS -X POST "${BASE_URL}/mortgage/${CASE_ID}/evidence/index" \
  -H "Content-Type: application/json" \
  -d "{\"documents\":[{\"document_id\":\"${DOCUMENT_ID}\"}],\"overwrite\":true}" \
  >/dev/null

UNDERWRITE_RESPONSE="$({
  cat <<'JSON'
{
  "payload": {
    "credit_score": 710,
    "monthly_income": 9000,
    "monthly_debt": 2600,
    "loan_amount": 280000,
    "property_value": 450000,
    "occupancy": "primary"
  },
  "model_version": "baseline_v1",
  "top_k": 5
}
JSON
} | curl -fsS -X POST "${BASE_URL}/mortgage/${CASE_ID}/underwrite" \
  -H "X-Request-Id: ${REQ_ID}" \
  -H "Content-Type: application/json" \
  -d @-)

TRACE_RESPONSE="$(curl -fsS "${BASE_URL}/mortgage/${CASE_ID}/underwrite/trace?request_id=${REQ_ID}")"

REPLAY_RESPONSE="$(curl -fsS -X POST "${BASE_URL}/mortgage/${CASE_ID}/underwrite/replay?request_id=${REQ_ID}")"

python - <<'PY' "${UNDERWRITE_RESPONSE}" "${REPLAY_RESPONSE}" "${TRACE_RESPONSE}" "${REQ_ID}"
import json
import sys

underwrite = json.loads(sys.argv[1])
replay = json.loads(sys.argv[2])
trace_wrapper = json.loads(sys.argv[3])
request_id = sys.argv[4]

citations = underwrite.get("justification", {}).get("citations", [])
first_chunk = citations[0]["chunk_id"] if citations else "none"

print("== Underwrite summary")
print(f"decision={underwrite.get('decision')}")
print(f"risk_score={underwrite.get('risk_score')}")
print(f"num_citations={len(citations)}")
print(f"first_citation_chunk_id={first_chunk}")

trace = trace_wrapper.get("trace", {})
trace_request_id = trace.get("request_id", "")
print(f"trace_request_id={trace_request_id}")
if trace_request_id != request_id:
    raise SystemExit("Trace request_id mismatch")

orig_chunks = [item.get("chunk_id") for item in citations]
replay_chunks = [
    item.get("chunk_id")
    for item in replay.get("justification", {}).get("citations", [])
]

if underwrite.get("decision") != replay.get("decision"):
    raise SystemExit("Replay decision mismatch")
if float(underwrite.get("risk_score", 0.0)) != float(replay.get("risk_score", 0.0)):
    raise SystemExit("Replay risk_score mismatch")
if orig_chunks != replay_chunks:
    raise SystemExit("Replay citation chunk_ids mismatch")

print("replay_check=ok")
PY
