# Multi-instance GLOSS deployment

Hosts N independent GLOSS instances on one Linux server, one per tutorial
participant, each reachable over SSH.

## Quick start

On the server, from a copy of this repo:

```bash
export GATEWAY_API_KEY="..."          # the Khoury gateway key
sudo -E ./deploy/provision.sh          # 10 instances
./deploy/verify.sh                     # fast checks
FULL=1 ./deploy/verify.sh              # adds a real query per instance
```

Credentials land in `deploy/participants.txt` (mode 600). Participants connect
with `ssh -p 220NN pNN@<server>` and run `python sensemaking_process.py`.

Knobs: `PARTICIPANTS`, `BASE_DIR`, `SSH_PORT_BASE`, `MEM_LIMIT`, `CPU_LIMIT`.
Start with `PARTICIPANTS=2` to validate before scaling up.

## How it fits together

```
host
├── dockerd  ────────────────────────────────┐
├── /srv/gloss/p01   (participant's checkout)│
│                                            │
├── container gloss-p01                      │
│   ├── sshd                :22 → host 22001 │
│   ├── conda env gloss-sensemaking          │
│   ├── /srv/gloss/p01      (same path!)     │
│   └── /var/run/docker.sock ────────────────┤ talks to the HOST daemon
│                                            │
└── container autogen-code-exec-<uuid>  ◄────┘ started BY gloss-p01,
    └── /workspace ← bind of /srv/gloss/p01    but a SIBLING on the host
```

GLOSS runs inside the participant container, but the code it generates runs in
a *sibling* container that the host daemon creates.

## The one constraint that will silently break this

`agents/coding_agent.py` passes `work_dir=REPO_ROOT` to
`DockerCommandLineCodeExecutor`, which does:

```python
volumes={str(self._bind_dir.resolve()): {"bind": "/workspace", "mode": "rw"}}
```

That path is resolved **inside the participant container**, then sent to the
**host** daemon, which resolves it again in its own filesystem. If the repo
lived at `/home/p01/GLOSS` in the container and `/srv/gloss/p01` on the host,
the host would mount something else, or create an empty directory, and the
generated code would run against no data — with no obvious error.

So the repo is mounted at an **identical absolute path** on both sides, and
`GLOSS_REPO_ROOT` is set to it. `deploy/verify.sh` checks this explicitly; it is
the check to run first when something inexplicable happens.

## Why each participant gets their own copy

The generated-code filename is fixed as `code_generation.py`
(`agents/agent_utils.py`), written into `work_dir`. Instances sharing a
directory would overwrite each other's code mid-run, and one participant could
execute another's. `provision.sh` rsyncs a template into `/srv/gloss/pNN` per
participant.

A broken instance is cheap to reset, without touching the others:

```bash
sudo rsync -a --delete /srv/gloss/_template/ /srv/gloss/p01/
sudo docker restart gloss-p01
```

## Environment gotchas, all handled by `entrypoint.sh`

| Variable | Value | Why |
|---|---|---|
| `RUNNING_IN_DOCKER` | **`false`** | This container *is* a container, but GLOSS runs here as the host side. `true` would send three code paths to `/workspace/sample_data`, which only exists in the executor container. |
| `GATEWAY_API_KEY` | the key | Written to `/etc/profile.d/`, because **sshd starts login shells with a fresh environment** — `docker run -e` alone is invisible to a participant who ssh's in. |
| `GLOSS_REPO_ROOT` | `/srv/gloss/pNN` | Sets the executor's `work_dir`; must match the host path. |
| `MPLBACKEND` | `Agg` | Two code paths call `plt.show()`, which fails headless. |
| `PATH` | env's bin first | Participants get the right `python` without `conda activate`. |

## Security posture

The host Docker socket is mounted into each participant container, which is
**equivalent to root on the host**. This was a deliberate trade for simplicity;
it is only acceptable because the box is disposable, holds nothing sensitive,
and participants are known attendees. Do not reuse this host for anything else,
and tear it down after the tutorial.

All instances share one gateway key (it is issued per machine), and any
participant can read it from their own environment. Rotate it afterwards.

## Operations

`gloss-janitor.timer` runs every 15 minutes to remove exited
`autogen-code-exec-*` containers, warn about executors running over an hour, and
warn when the root filesystem passes 80%. Normal runs already clean up after
themselves (`auto_remove=True`); this catches interrupted ones.

```bash
sudo systemctl list-timers gloss-janitor.timer
sudo journalctl -u gloss-janitor.service --since -1h
docker ps -a --filter name=autogen-code-exec
```

## Concurrency

All instances share **one** `gemma4:31b` on the Khoury cluster, and each query
is many sequential LLM calls. Expect latency to grow non-linearly with
simultaneous users. Measure before the event:

```bash
for i in 01 02 03 04 05 06 07 08 09 10; do
  ( docker exec -u p$i gloss-p$i bash -lc \
      "cd /srv/gloss/p$i && time python sensemaking_process.py" \
      > /tmp/load_$i.log 2>&1 & )
done; wait
grep -h real /tmp/load_*.log
```

If it degrades badly: split participants into two groups, raise
`LOCAL_MODEL_TIMEOUT`, or ask the cluster admin for more workers holding the
model.
