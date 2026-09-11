#!/bin/bash
# Provision N GLOSS tutorial instances on this host.
#
# Run on the SERVER, from a copy of the repo, as a user with sudo. Idempotent:
# safe to re-run after changing the code or the participant count.
#
#   sudo ./deploy/provision.sh                 # 10 participants, default key
#   PARTICIPANTS=4 sudo ./deploy/provision.sh  # smaller dry run first
#
# Reads GATEWAY_API_KEY from the environment; passwords are generated and
# written to deploy/participants.txt for you to hand out.
set -euo pipefail

PARTICIPANTS="${PARTICIPANTS:-10}"
BASE_DIR="${BASE_DIR:-/srv/gloss}"
SSH_PORT_BASE="${SSH_PORT_BASE:-22000}"
EXECUTOR_IMAGE="${EXECUTOR_IMAGE:-gloss-sensemaking-code}"
PARTICIPANT_IMAGE="${PARTICIPANT_IMAGE:-gloss-tutorial}"
MEM_LIMIT="${MEM_LIMIT:-2g}"
CPU_LIMIT="${CPU_LIMIT:-3}"

REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS_FILE="${REPO_SRC}/deploy/participants.txt"

if [[ -z "${GATEWAY_API_KEY:-}" ]]; then
    echo "ERROR: GATEWAY_API_KEY is not set. Export it before running." >&2
    exit 1
fi

echo "==> Repo source:  $REPO_SRC"
echo "==> Instances:    $PARTICIPANTS"
echo "==> Base dir:     $BASE_DIR"

# --- 1. Docker -------------------------------------------------------------
if ! command -v docker &>/dev/null; then
    echo "==> Installing Docker"
    apt-get update -qq
    apt-get install -y -qq docker.io
    systemctl enable --now docker
fi
docker version --format '==> Docker server {{.Server.Version}}'

# --- 2. Verify the model gateway is reachable FROM THIS HOST ---------------
# Everything downstream is pointless if this fails, so fail loudly now.
echo "==> Checking model gateway"
CODE="$(curl -s -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${GATEWAY_API_KEY}" \
    https://compute-gateway.europa.khoury.northeastern.edu/api/tags || true)"
if [[ "$CODE" != "200" ]]; then
    echo "ERROR: gateway returned HTTP $CODE (expected 200)." >&2
    echo "       403 with an HTML body means this host's IP is not allowlisted." >&2
    exit 1
fi
echo "==> Gateway OK (HTTP 200)"

# --- 3. Images -------------------------------------------------------------
# The executor image needs no credentials: generated code only reads CSVs and
# calls data functions, it never makes an LLM call.
echo "==> Building $EXECUTOR_IMAGE (code executor)"
docker build -q -f "${REPO_SRC}/Dockerfile" -t "$EXECUTOR_IMAGE" "$REPO_SRC"

echo "==> Building $PARTICIPANT_IMAGE (participant environment)"
docker build -q -f "${REPO_SRC}/deploy/Dockerfile.participant" -t "$PARTICIPANT_IMAGE" "$REPO_SRC"

# --- 4. Per-participant checkouts -----------------------------------------
# Each participant needs their OWN copy: the generated-code filename is fixed
# as code_generation.py (agents/agent_utils.py), so instances sharing a
# directory would overwrite each other's code mid-run.
mkdir -p "$BASE_DIR"
TEMPLATE="${BASE_DIR}/_template"
echo "==> Syncing template to $TEMPLATE"
rsync -a --delete \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude 'sample_data_old' \
    --exclude 'deploy/participants.txt*' \
    --exclude 'code_generation.py' \
    --exclude 'code_generation.sh' \
    "${REPO_SRC}/" "${TEMPLATE}/"

# Passwords are reused when a credentials file already exists, so re-running
# this script (to pick up a code change, or to recreate a wedged instance) does
# not invalidate a handout that has already been printed and distributed.
declare -A EXISTING_PASSWORDS=()
if [[ -f "$CREDS_FILE" ]]; then
    while read -r -a fields; do
        u="${fields[0]:-}"
        # The password is always the last column, so this tolerates both the
        # older 3-column file and the current 4-column one.
        pw="${fields[-1]:-}"
        [[ "$u" == "user" || -z "$u" || -z "$pw" || "$u" == "$pw" ]] && continue
        EXISTING_PASSWORDS["$u"]="$pw"
    done < "$CREDS_FILE"
    if [[ ${#EXISTING_PASSWORDS[@]} -gt 0 ]]; then
        echo "==> Reusing ${#EXISTING_PASSWORDS[@]} existing password(s) from $CREDS_FILE"
    fi
fi

: > "$CREDS_FILE"
chmod 600 "$CREDS_FILE"
printf '%-6s %-7s %-8s %s\n' "user" "port" "uiport" "password" >> "$CREDS_FILE"

for i in $(seq -w 1 "$PARTICIPANTS"); do
    USER_NAME="p${i}"
    # Path is IDENTICAL on host and inside the container. This is required: the
    # code executor's bind mount is resolved by the HOST daemon, so a container
    # path with no host equivalent would mount the wrong thing or nothing.
    REPO_PATH="${BASE_DIR}/${USER_NAME}"
    PORT=$((SSH_PORT_BASE + 10#$i))
    # Generated without a pipeline on purpose: `tr < /dev/urandom | head -c N`
    # makes head exit early, tr die on SIGPIPE, and `set -o pipefail` abort the
    # whole script silently. Characters are limited to unambiguous lowercase and
    # digits so passwords can be read off a slide without confusion.
    PASSWORD="${EXISTING_PASSWORDS[$USER_NAME]:-}"
    if [[ -z "$PASSWORD" ]]; then
        PASSWORD="$(python3 -c "import secrets
alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'
print(''.join(secrets.choice(alphabet) for _ in range(6)) + '-' +
      ''.join(secrets.choice(alphabet) for _ in range(6)))")"
    fi

    echo "==> ${USER_NAME}: ${REPO_PATH} on port ${PORT}"
    rsync -a --delete "${TEMPLATE}/" "${REPO_PATH}/"

    docker rm -f "gloss-${USER_NAME}" &>/dev/null || true
    docker run -d \
        --name "gloss-${USER_NAME}" \
        --restart unless-stopped \
        --memory "$MEM_LIMIT" --cpus "$CPU_LIMIT" \
        -p "${PORT}:22" \
        -p "$((8500 + 10#$i)):8501" \
        -v "${REPO_PATH}:${REPO_PATH}" \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -e "PARTICIPANT_USER=${USER_NAME}" \
        -e "PARTICIPANT_PASSWORD=${PASSWORD}" \
        -e "GLOSS_REPO_ROOT=${REPO_PATH}" \
        -e "GATEWAY_API_KEY=${GATEWAY_API_KEY}" \
        -e "DOCKER_NAME=${EXECUTOR_IMAGE}" \
        -e "MPLBACKEND=Agg" \
        "$PARTICIPANT_IMAGE" >/dev/null

    printf '%-6s %-7s %-8s %s\n' "$USER_NAME" "$PORT" "$((8500 + 10#$i))" "$PASSWORD" >> "$CREDS_FILE"
done

# --- 5. Protect the executor image ----------------------------------------
# The executor image exists only locally. If anything prunes it, autogen's
# start() falls back to client.images.pull(), which fails against Docker Hub and
# breaks code generation for every participant at once. An idle container
# referencing the image makes it unprunable, and the tarball turns a 20-minute
# rebuild into a 2-minute restore.
if ! docker ps --format '{{.Names}}' | grep -qx gloss-image-pin; then
    docker rm -f gloss-image-pin &>/dev/null || true
    docker run -d --name gloss-image-pin --restart unless-stopped \
        --entrypoint /bin/sh "$EXECUTOR_IMAGE" -c 'sleep infinity' >/dev/null
    echo "==> Pinned $EXECUTOR_IMAGE against pruning"
fi

BACKUP="${BASE_DIR}/images-backup.tgz"
if [[ ! -f "$BACKUP" ]]; then
    echo "==> Saving image backup to $BACKUP (one-off, a few minutes)"
    docker save "$EXECUTOR_IMAGE" "$PARTICIPANT_IMAGE" | gzip > "$BACKUP"
fi

# --- 6. Janitor ------------------------------------------------------------
echo "==> Installing container janitor timer"
install -m 0755 "${REPO_SRC}/deploy/gloss-janitor.sh" /usr/local/bin/gloss-janitor.sh
install -m 0644 "${REPO_SRC}/deploy/gloss-janitor.service" /etc/systemd/system/
install -m 0644 "${REPO_SRC}/deploy/gloss-janitor.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now gloss-janitor.timer

# Hand the credentials file back to the invoking user so it can be read without
# sudo, keeping it mode 600.
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "${SUDO_USER}:${SUDO_USER}" "$CREDS_FILE" || true
fi

echo
echo "==> Done. ${PARTICIPANTS} instances running."
echo "==> Credentials: ${CREDS_FILE}"
echo "==> Verify with: ./deploy/verify.sh"
