#!/bin/bash
# Container start-up for one tutorial participant.
#
# Three jobs that all have to happen before sshd starts:
#   1. create the participant account with the password passed in
#   2. export the container's env into SSH login sessions -- sshd starts login
#      shells with a fresh environment, so `docker run -e FOO=bar` is NOT
#      visible to a participant who ssh's in. This is the single most common way
#      to get a container that looks fine but fails every query.
#   3. make the mounted host Docker socket usable by a non-root user
set -euo pipefail

PARTICIPANT="${PARTICIPANT_USER:?PARTICIPANT_USER must be set}"
PASSWORD="${PARTICIPANT_PASSWORD:?PARTICIPANT_PASSWORD must be set}"
REPO="${GLOSS_REPO_ROOT:?GLOSS_REPO_ROOT must be set}"

# --- 1. account ------------------------------------------------------------
if ! id "$PARTICIPANT" &>/dev/null; then
    useradd --create-home --shell /bin/bash "$PARTICIPANT"
fi
echo "${PARTICIPANT}:${PASSWORD}" | chpasswd

# Generated code runs as root in the executor container (autogen calls exec_run
# with no user), so anything it writes lands root-owned in this bind mount.
# Without sudo a participant cannot delete or edit their own generated files.
# Non-fatal: a missing sudo package must not crash-loop the container, since
# everything else here still gives a working instance.
if command -v sudo &>/dev/null; then
    mkdir -p /etc/sudoers.d
    echo "${PARTICIPANT} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/${PARTICIPANT}"
    chmod 0440 "/etc/sudoers.d/${PARTICIPANT}"
else
    echo "WARNING: sudo not installed; ${PARTICIPANT} cannot clean root-owned files." >&2
fi

# --- 2. environment for login shells --------------------------------------
# Only variables GLOSS actually reads. Deliberately NOT exporting
# RUNNING_IN_DOCKER as true: this container is where GLOSS runs as the host
# side, and a true value would send three code paths looking for
# /workspace/sample_data, which only exists in the code-executor container.
{
    echo "# Written by deploy/entrypoint.sh at container start."
    echo "export GATEWAY_API_KEY='${GATEWAY_API_KEY:-}'"
    echo "export GLOSS_REPO_ROOT='${REPO}'"
    echo "export DOCKER_NAME='${DOCKER_NAME:-gloss-sensemaking-code}'"
    echo "export MPLBACKEND='${MPLBACKEND:-Agg}'"
    echo "export RUNNING_IN_DOCKER='false'"
    echo "export LOCAL_MODEL_NAME='${LOCAL_MODEL_NAME:-gemma4:31b}'"
    echo "export LOCAL_MODEL_TIMEOUT='${LOCAL_MODEL_TIMEOUT:-600}'"
    echo "cd '${REPO}' 2>/dev/null || true"
} > /etc/profile.d/10-gloss-env.sh
chmod 0644 /etc/profile.d/10-gloss-env.sh

# --- 3. host Docker socket access -----------------------------------------
# The socket arrives owned by the host's docker group, whose GID does not exist
# in this image. Create a matching group and put the participant in it, rather
# than chmod 666 on a root-equivalent socket.
if [[ -S /var/run/docker.sock ]]; then
    SOCK_GID="$(stat -c '%g' /var/run/docker.sock)"
    if ! getent group "$SOCK_GID" &>/dev/null; then
        groupadd --gid "$SOCK_GID" dockerhost
    fi
    usermod --append --groups "$(getent group "$SOCK_GID" | cut -d: -f1)" "$PARTICIPANT"
else
    echo "WARNING: /var/run/docker.sock is not mounted; code generation will fail." >&2
fi

# The participant owns their own checkout so they can edit the query and so the
# code executor can write code_generation.py into it.
if [[ -d "$REPO" ]]; then
    chown -R "$PARTICIPANT":"$PARTICIPANT" "$REPO" || \
        echo "WARNING: could not chown $REPO" >&2
else
    echo "WARNING: $REPO is not mounted." >&2
fi

cat > /etc/motd <<MOTD

  GLOSS tutorial -- you are ${PARTICIPANT}. Your copy of the code: ${REPO}

  Run a query:      python sensemaking_process.py
  Edit the query:   the bottom of sensemaking_process.py
  Check the model:  python -m agents.local_model
  Your user id in the data is:  user1

  Note: the CODE GENERATION step prints nothing at all while it runs.
  Up to a few minutes of silence there is normal, not a hang.

  Please do not run docker commands -- you don't need to, and they
  affect the other participants.

MOTD

echo "Participant '$PARTICIPANT' ready; repo at $REPO. Starting sshd."
exec /usr/sbin/sshd -D -e
