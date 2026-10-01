#!/bin/sh
# Smoke test: one real embedding and one real generation against Ollama.
#
# It answers "does the model path work at all, and how fast": host -> port ->
# Ollama -> model files in the volume -> loaded onto GPU/CPU -> output. It does
# not test Qdrant or answer quality.
#
# Usually run through `make smoke`, which passes the settings from .env. Needs
# only sh, curl and awk, so it runs anywhere make does without extra installs.
#
# Exit status is non-zero if either request fails.

set -u

OLLAMA_URL=${OLLAMA_URL:-http://127.0.0.1:11434}
LLM_MODEL=${LLM_MODEL:-qwen3:1.7b}
EMBEDDING_MODEL=${EMBEDDING_MODEL:-nomic-embed-text}
# The first request after startup also loads the model from disk, which on a
# slow disk or under memory pressure can take minutes, so these are generous.
EMBED_TIMEOUT=${SMOKE_EMBED_TIMEOUT:-180}
GENERATE_TIMEOUT=${SMOKE_GENERATE_TIMEOUT:-300}

body=$(mktemp)
trap 'rm -f "$body"' EXIT

failures=0

# post PATH JSON TIMEOUT
# Sends the request, writes the response body to $body and the HTTP status to
# $status (000 when there was no HTTP response at all). Returns curl's exit code.
post() {
    status=$(curl -s -o "$body" -w '%{http_code}' --max-time "$3" \
        -H 'Content-Type: application/json' -d "$2" "$OLLAMA_URL$1")
}

# field num KEY -> integer value of "KEY":123
# field str KEY -> string value of "KEY":"...", with JSON escapes resolved
# field dim     -> length of the first vector in "embeddings":[[...]]
#
# Ollama answers with a single line of compact JSON of a known shape, which awk
# can pick apart reliably enough for a smoke test.
field() {
    awk -v mode="$1" -v key="${2:-}" '
        mode == "num" {
            if (match($0, "\"" key "\":[0-9]+")) {
                s = substr($0, RSTART, RLENGTH); sub(/^.*:/, "", s); print s
            }
        }
        mode == "str" {
            i = index($0, "\"" key "\":\"")
            if (i == 0) next
            s = substr($0, i + length(key) + 4)
            out = ""
            for (j = 1; j <= length(s); j++) {
                c = substr(s, j, 1)
                if (c == "\\") {
                    j++; c = substr(s, j, 1)
                    if (c == "n" || c == "t") c = " "
                } else if (c == "\"") {
                    break
                }
                out = out c
            }
            print out
        }
        mode == "dim" {
            i = index($0, "\"embeddings\":[[")
            if (i == 0) next
            s = substr($0, i + 15)
            s = substr(s, 1, index(s, "]") - 1)
            print gsub(/,/, "", s) + 1
        }
    ' "$body"
}

# Ollama reports durations in nanoseconds.
secs() {
    awk -v ns="${1:-0}" 'BEGIN { printf "%.1fs", ns / 1e9 }'
}

speed() {
    awk -v n="${1:-0}" -v ns="${2:-0}" \
        'BEGIN { if (n > 0 && ns > 0) printf "%.1f tok/s", n / (ns / 1e9); else printf "n/a" }'
}

# fail LABEL MODEL CURL_EXIT TIMEOUT
fail() {
    if [ "$3" -eq 28 ]; then
        reason="no response within ${4}s"
    elif [ "$status" = 000 ]; then
        reason="cannot reach $OLLAMA_URL (curl exit $3) - is the stack up? try: make up"
    elif [ "$status" = 200 ]; then
        reason="HTTP 200 but the response had an unexpected shape"
    else
        err=$(field str error)
        reason="HTTP $status${err:+: $err}"
    fi
    printf '%-11s %-20s FAILED  %s\n' "$1" "$2" "$reason"
    failures=$((failures + 1))
}

echo "Ollama at $OLLAMA_URL"
echo "(the first request after startup also loads the model, which is the slow part)"

# ------------------------------------------------------------------ embedding
post /api/embed \
    "{\"model\":\"$EMBEDDING_MODEL\",\"input\":\"What does lm() return?\"}" \
    "$EMBED_TIMEOUT"
rc=$?
dim=$(field dim)
if [ "$rc" -eq 0 ] && [ "$status" = 200 ] && [ -n "$dim" ]; then
    printf '%-11s %-20s OK      dim=%s  load=%s  total=%s\n' \
        embedding "$EMBEDDING_MODEL" "$dim" \
        "$(secs "$(field num load_duration)")" "$(secs "$(field num total_duration)")"
else
    fail embedding "$EMBEDDING_MODEL" "$rc" "$EMBED_TIMEOUT"
fi

# ----------------------------------------------------------------- generation
prompt='In one sentence, what does the R function lm() do?'
# "think": false stops reasoning models such as Qwen3 from writing a hidden
# chain of thought first, which is many times slower than the answer itself.
post /api/generate \
    "{\"model\":\"$LLM_MODEL\",\"prompt\":\"$prompt\",\"stream\":false,\"think\":false}" \
    "$GENERATE_TIMEOUT"
rc=$?
# Models without thinking support may reject the "think" field; retry without it.
if [ "$rc" -eq 0 ] && [ "$status" = 400 ] && field str error | grep -qi think; then
    post /api/generate \
        "{\"model\":\"$LLM_MODEL\",\"prompt\":\"$prompt\",\"stream\":false}" \
        "$GENERATE_TIMEOUT"
    rc=$?
fi
answer=$(field str response)
if [ "$rc" -eq 0 ] && [ "$status" = 200 ] && [ -n "$answer" ]; then
    tokens=$(field num eval_count)
    printf '%-11s %-20s OK      load=%s  tokens=%s  speed=%s  total=%s\n' \
        generation "$LLM_MODEL" \
        "$(secs "$(field num load_duration)")" "${tokens:-?}" \
        "$(speed "$tokens" "$(field num eval_duration)")" \
        "$(secs "$(field num total_duration)")"
    printf '%-11s answer: %s\n' '' "$(printf '%s' "$answer" | cut -c1-300)"
else
    fail generation "$LLM_MODEL" "$rc" "$GENERATE_TIMEOUT"
fi

[ "$failures" -eq 0 ]
