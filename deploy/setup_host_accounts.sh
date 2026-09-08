#!/bin/bash
# Create host accounts that log participants straight into their container.
#
# Needed because the provider's firewall only permits the main SSH port, so the
# containers' published ports (22001..22010) are unreachable from outside.
# Participants therefore connect to the normal SSH port as pNN, and their login
# shell (deploy/gloss-shell) execs into container gloss-pNN.
#
# Run on the SERVER as root, after provision.sh:
#   sudo ./deploy/setup_host_accounts.sh
#
# Reuses the passwords already generated in deploy/participants.txt so the
# handout stays correct.
set -euo pipefail

REPO_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CREDS_FILE="${REPO_SRC}/deploy/participants.txt"
SHELL_PATH=/usr/local/bin/gloss-shell

[[ -f "$CREDS_FILE" ]] || { echo "ERROR: $CREDS_FILE not found; run provision.sh first" >&2; exit 1; }

install -m 0755 "${REPO_SRC}/deploy/gloss-shell" "$SHELL_PATH"
grep -qxF "$SHELL_PATH" /etc/shells || echo "$SHELL_PATH" >> /etc/shells

# The host account needs docker access to exec into its container. This is
# root-equivalent, which is already true of the socket mounted into each
# container, so it adds no new exposure on this disposable host.
getent group docker >/dev/null || groupadd docker

created=0
while read -r user port password; do
    [[ "$user" == "user" || -z "${user:-}" ]] && continue     # skip header
    id "$user" &>/dev/null || useradd --create-home --shell "$SHELL_PATH" "$user"
    usermod --shell "$SHELL_PATH" --append --groups docker "$user"
    echo "${user}:${password}" | chpasswd
    echo "==> ${user} ready (password from participants.txt)"
    created=$((created + 1))
done < "$CREDS_FILE"

echo
echo "==> ${created} host accounts configured."
echo "==> Participants connect with:  ssh -p <main-ssh-port> pNN@<server>"
echo "==> Their login lands inside gloss-pNN at /srv/gloss/pNN."
