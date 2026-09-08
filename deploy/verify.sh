#!/bin/bash
# Verify every tutorial instance, cheapest checks first.
#
# Run on the SERVER after provision.sh:
#   ./deploy/verify.sh          # checks 1-5, no LLM calls, fast
#   FULL=1 ./deploy/verify.sh   # adds a real end-to-end query per instance
set -uo pipefail

PARTICIPANTS="${PARTICIPANTS:-10}"
BASE_DIR="${BASE_DIR:-/srv/gloss}"
EXECUTOR_IMAGE="${EXECUTOR_IMAGE:-gloss-sensemaking-code}"
FULL="${FULL:-0}"

PASS=0
FAIL=0
note() { printf '  %-46s %s\n' "$1" "$2"; }
ok()   { note "$1" "OK ${2:-}"; PASS=$((PASS+1)); }
bad()  { note "$1" "FAIL ${2:-}"; FAIL=$((FAIL+1)); }

echo "=== Host checks ==="
docker images -q "$EXECUTOR_IMAGE" | grep -q . \
    && ok "executor image present" || bad "executor image present"

CODE="$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${GATEWAY_API_KEY:-}" \
    https://compute-gateway.europa.khoury.northeastern.edu/api/tags || true)"
[[ "$CODE" == "200" ]] && ok "model gateway reachable" "(HTTP $CODE)" \
                       || bad "model gateway reachable" "(HTTP $CODE)"

systemctl is-active --quiet gloss-janitor.timer \
    && ok "janitor timer active" || bad "janitor timer active"

for i in $(seq -w 1 "$PARTICIPANTS"); do
    USER_NAME="p${i}"
    C="gloss-${USER_NAME}"
    REPO_PATH="${BASE_DIR}/${USER_NAME}"
    echo
    echo "=== ${USER_NAME} ==="

    if ! docker ps --format '{{.Names}}' | grep -qx "$C"; then
        bad "container running"
        continue
    fi
    ok "container running"

    # The repo must be visible at the SAME path inside the container as on the
    # host, or the code executor's bind mount resolves to nothing host-side.
    docker exec "$C" test -f "${REPO_PATH}/sensemaking_process.py" \
        && ok "repo at identical path" "($REPO_PATH)" \
        || bad "repo at identical path" "($REPO_PATH)"

    # Env must reach LOGIN shells, not just PID 1 -- sshd resets the
    # environment, so this is what a participant will actually see.
    docker exec "$C" bash -lc 'test -n "$GATEWAY_API_KEY"' \
        && ok "gateway key in login shell" || bad "gateway key in login shell"

    docker exec "$C" bash -lc '[ "$RUNNING_IN_DOCKER" = "false" ]' \
        && ok "RUNNING_IN_DOCKER=false" || bad "RUNNING_IN_DOCKER=false"

    docker exec "$C" bash -lc 'python -c "import langchain_openai, autogen_core"' &>/dev/null \
        && ok "python env importable" || bad "python env importable"

    N="$(docker exec "$C" bash -lc \
        'python -c "from agents.database_registry import get_all_databases; print(len(get_all_databases()))"' \
        2>/dev/null | tr -dc '0-9')"
    [[ "$N" == "5" ]] && ok "5 databases registered" || bad "databases registered" "(got '${N:-none}')"

    SMS="$(docker exec "$C" bash -lc \
        'python -c "
from data_streams.sms_data import get_sms_stats
s=get_sms_stats(\"user1\",\"2020-11-02 00:00:00\",\"2020-11-02 23:59:59\")
print(s[\"total_messages\"], s[\"total_messages_incoming\"], s[\"total_messages_outgoing\"])"' \
        2>/dev/null | tail -1)"
    [[ "$SMS" == "37 17 20" ]] && ok "sample data correct" "($SMS)" \
                              || bad "sample data correct" "(got '${SMS:-none}')"

    # Participants reach the host daemon through the mounted socket.
    docker exec -u "$USER_NAME" "$C" docker images -q "$EXECUTOR_IMAGE" 2>/dev/null | grep -q . \
        && ok "participant can reach docker" || bad "participant can reach docker"

    if [[ "$FULL" == "1" ]]; then
        echo "  running a real query (slow)..."
        OUT="$(docker exec -u "$USER_NAME" "$C" bash -lc \
            "cd '${REPO_PATH}' && timeout 900 python sensemaking_process.py" 2>&1 | tail -40)"
        grep -q "FINAL ANSWER" <<<"$OUT" \
            && ok "end-to-end query" || bad "end-to-end query"
        grep -qi "youtube" <<<"$OUT" && ok "answer plausible" || note "answer plausible" "check manually"
    fi
done

echo
echo "=== ${PASS} passed, ${FAIL} failed ==="
[[ "$FAIL" -eq 0 ]]
