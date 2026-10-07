#!/bin/bash
# Print the PID of whatever is listening on a port.
#
#   ./port_pid.sh            # port 8501, the dashboard
#   ./port_pid.sh 8601
#   kill $(./port_pid.sh)    # stop it
#
# Mostly needed after a dropped connection: the dashboard keeps running inside
# the container, still holding the port, and the next `streamlit run` fails
# with "Port 8501 is already in use".
#
# Reads /proc directly rather than using lsof, ss or fuser, none of which are
# installed in the participant image.

PORT=${1:-8501}
HEX_PORT=$(printf '%04X' "$PORT")

# /proc/net/tcp lists local address as HEX_IP:HEX_PORT, and state 0A is LISTEN.
# Field 10 is the socket's inode, which is what links it back to a process.
INODE=$(awk -v port=":$HEX_PORT" '
    $2 ~ port && $4 == "0A" {print $10; exit}
' /proc/net/tcp)

if [ -z "$INODE" ]; then
    echo "No process listening on port $PORT" >&2
    exit 1
fi

# Each process's open sockets appear in /proc/<pid>/fd as symlinks to
# socket:[inode], so the owner is whichever one points at ours.
for pid_dir in /proc/[0-9]*; do
    PID=${pid_dir#/proc/}

    if ls -l "$pid_dir/fd" 2>/dev/null | grep -q "socket:\[$INODE\]"; then
        echo "$PID"
        exit 0
    fi
done

# Reachable when the socket belongs to another user's process, whose /proc/<pid>/fd
# is not readable here.
echo "Socket found on port $PORT, but the process could not be identified." >&2
exit 1
