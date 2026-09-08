#!/bin/bash
# Reap orphaned code-executor containers.
#
# agents/coding_agent.py now runs the executor with auto_remove=True, so normal
# runs clean up after themselves. This is the safety net for the abnormal ones:
# a participant Ctrl-C'ing mid-query, or an SSH session dropping, leaves the
# container behind. Ten participants doing that repeatedly fills the disk.
set -euo pipefail

# Only ever touches containers autogen created (it names them
# autogen-code-exec-<uuid4>), and only ones that have already exited.
ORPHANS="$(docker ps -aq \
    --filter 'name=autogen-code-exec' \
    --filter 'status=exited' 2>/dev/null || true)"

if [[ -n "$ORPHANS" ]]; then
    COUNT="$(echo "$ORPHANS" | wc -l | tr -d ' ')"
    echo "Removing ${COUNT} exited executor container(s)"
    echo "$ORPHANS" | xargs -r docker rm >/dev/null
else
    echo "No exited executor containers"
fi

# A run that is still going has a live container, so never remove running ones.
# Report long-lived ones instead: over an hour means something is wedged.
STUCK="$(docker ps -q --filter 'name=autogen-code-exec' 2>/dev/null || true)"
if [[ -n "$STUCK" ]]; then
    echo "$STUCK" | while read -r id; do
        STARTED="$(docker inspect -f '{{.State.StartedAt}}' "$id")"
        AGE=$(( $(date +%s) - $(date -d "$STARTED" +%s) ))
        if (( AGE > 3600 )); then
            echo "WARNING: executor container $id has run for ${AGE}s"
        fi
    done
fi

USED="$(df --output=pcent / | tail -1 | tr -dc '0-9')"
if (( USED > 80 )); then
    echo "WARNING: root filesystem ${USED}% full"
fi
