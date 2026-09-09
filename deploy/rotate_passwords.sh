#!/bin/bash
# Issue fresh passwords to every participant.
#
# Participants authenticate to the HOST account pNN (their login shell then
# execs into their container), so rotating a password is just chpasswd plus a
# rewrite of the credentials file. No container is recreated and no session in
# progress is disturbed -- the container's own PARTICIPANT_PASSWORD is never
# used for login.
#
#   sudo ./deploy/rotate_passwords.sh
#
# The previous credentials file is kept alongside, timestamped, in case a
# handout has already gone out and you need to compare.
set -euo pipefail

BASE_DIR="${BASE_DIR:-/srv/gloss}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS_FILE="${SRC}/deploy/participants.txt"
STAMP="$(date +%Y%m%d-%H%M%S)"

[[ -f "$CREDS_FILE" ]] || { echo "ERROR: $CREDS_FILE not found" >&2; exit 1; }

cp -p "$CREDS_FILE" "${CREDS_FILE}.${STAMP}.bak"
echo "==> Previous credentials saved to ${CREDS_FILE}.${STAMP}.bak"

new_password() {
    # No pipeline: `tr < /dev/urandom | head -c N` makes head exit early, tr
    # die on SIGPIPE, and `set -o pipefail` abort the script. Unambiguous
    # characters only, so a password can be read off a slide.
    python3 -c "import secrets
alphabet = 'abcdefghijkmnpqrstuvwxyz23456789'
print(''.join(secrets.choice(alphabet) for _ in range(6)) + '-' +
      ''.join(secrets.choice(alphabet) for _ in range(6)))"
}

# Rewrite the file, keeping each participant's existing ports and only
# replacing the password column.
TMP="$(mktemp)"
printf '%-6s %-7s %-8s %s\n' "user" "port" "uiport" "password" > "$TMP"

rotated=0
while read -r -a fields; do
    user="${fields[0]:-}"
    [[ "$user" == "user" || -z "$user" ]] && continue
    port="${fields[1]:-}"
    uiport="${fields[2]:-}"
    # Tolerate the older 3-column format, where column 3 was the password.
    if [[ "${#fields[@]}" -lt 4 ]]; then
        uiport="$((8500 + 10#${user#p}))"
    fi

    password="$(new_password)"
    if id "$user" &>/dev/null; then
        echo "${user}:${password}" | chpasswd
        echo "==> ${user}: password rotated"
        rotated=$((rotated + 1))
    else
        echo "==> ${user}: no host account, recorded but not applied" >&2
    fi
    printf '%-6s %-7s %-8s %s\n' "$user" "$port" "$uiport" "$password" >> "$TMP"
done < "${CREDS_FILE}.${STAMP}.bak"

install -m 600 "$TMP" "$CREDS_FILE"
rm -f "$TMP"
if [[ -n "${SUDO_USER:-}" ]]; then
    chown "${SUDO_USER}:${SUDO_USER}" "$CREDS_FILE" || true
fi

echo
echo "==> ${rotated} password(s) rotated. New credentials: ${CREDS_FILE}"
echo "==> Regenerate the handout so it matches:"
echo "      python3 deploy/make_handout.py --host <server> --port <ssh-port>"
