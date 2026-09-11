#!/bin/bash
# Distribute code changes to every participant instance.
#
# Use this for code changes; it is much lighter than provision.sh. The images
# contain no application code (the Dockerfile copies only environment_linux.yml)
# and each checkout is bind-mounted, so updated files are live immediately --
# no image rebuild and no container restart.
#
# Only a change to environment_linux.yml needs provision.sh, which rebuilds the
# images and recreates the containers.
#
#   sudo ./deploy/update_instances.sh                  # dry run: show what would change
#   sudo ./deploy/update_instances.sh --apply          # distribute
#   sudo ./deploy/update_instances.sh --apply --force  # also delete files removed upstream
#
# Participants' own edits to a file that also changed upstream are overwritten,
# but a copy is kept under /srv/gloss/_backups/. Files a participant created
# that do not exist upstream are left alone unless --force is given.
set -euo pipefail

BASE_DIR="${BASE_DIR:-/srv/gloss}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${BASE_DIR}/_template"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="${BASE_DIR}/_backups"

APPLY=0
FORCE=0
for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        --force) FORCE=1 ;;
        -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

# Never distribute credentials, generated handouts, or run artifacts.
EXCLUDES=(
    --exclude '.git'
    --exclude '__pycache__'
    --exclude '*.pyc'
    --exclude 'sample_data_old'
    --exclude 'deploy/participants.txt*'
    --exclude 'deploy/GLOSS-tutorial-logins.pdf'
    --exclude 'deploy/GLOSS-tutorial-logins.html'
    --exclude 'code_generation.py'
    --exclude 'code_generation.sh'
    --exclude 'tmp_code_*'
    --exclude 'streamlit.log'
    --exclude '.streamlit/secrets.toml'
)

[[ -f "${SRC}/sensemaking_process.py" ]] || {
    echo "ERROR: ${SRC} does not look like a GLOSS checkout" >&2; exit 1; }

echo "==> Source:   $SRC"
echo "==> Template: $TEMPLATE"
if [[ "$APPLY" -eq 0 ]]; then
    echo "==> DRY RUN (nothing will be written; pass --apply to distribute)"
fi

DRY=()
[[ "$APPLY" -eq 0 ]] && DRY=(--dry-run)

# --- 1. source -> template -------------------------------------------------
echo
echo "==> Updating template"
rsync -a --delete "${DRY[@]}" "${EXCLUDES[@]}" \
    --itemize-changes "${SRC}/" "${TEMPLATE}/" | grep -vE '^\.d' || true

# --- 2. template -> each participant --------------------------------------
DELETE=()
[[ "$FORCE" -eq 1 ]] && DELETE=(--delete)

shopt -s nullglob
for repo in "${BASE_DIR}"/p[0-9][0-9]; do
    participant="$(basename "$repo")"
    container="gloss-${participant}"

    # Files must end up owned by the participant's uid INSIDE the container,
    # which is not the same as the host account's uid. Read it from the
    # container rather than assuming.
    uid="$(docker exec "$container" id -u "$participant" 2>/dev/null || echo "")"
    if [[ -z "$uid" ]]; then
        uid="$(stat -c '%u' "$repo" 2>/dev/null || echo 1000)"
        echo "  (${participant}: container not running; using existing owner uid ${uid})"
    fi

    backup=("--backup" "--backup-dir=${BACKUP_ROOT}/${participant}-${STAMP}")
    [[ "$APPLY" -eq 0 ]] && backup=()

    changes="$(rsync -a "${DRY[@]}" "${EXCLUDES[@]}" "${DELETE[@]}" "${backup[@]}" \
        --itemize-changes "${TEMPLATE}/" "${repo}/" | grep -vE '^\.d|^$' || true)"

    if [[ -z "$changes" ]]; then
        echo "  ${participant}: already up to date"
    else
        count="$(wc -l <<<"$changes" | tr -d ' ')"
        echo "  ${participant}: ${count} file(s)"
        sed 's/^/      /' <<<"$changes" | head -12
        [[ "$count" -gt 12 ]] && echo "      ... and $((count - 12)) more"
    fi

    if [[ "$APPLY" -eq 1 ]]; then
        chown -R "${uid}:${uid}" "$repo"
    fi
done

echo
if [[ "$APPLY" -eq 1 ]]; then
    echo "==> Distributed. Changes are live immediately (the checkouts are bind-mounted)."
    echo "==> Any overwritten participant files are under ${BACKUP_ROOT}/*-${STAMP}/"
    echo "==> Participants running a query right now should re-run it to pick up changes."
else
    echo "==> Dry run complete. Re-run with --apply to distribute."
fi
