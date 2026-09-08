#!/usr/bin/env python3
"""
Build the maintainer/operations PDF for the tutorial deployment.

    python3 deploy/make_maintainer_doc.py --host 207.56.9.25 --port 65173 --admin tutorial

Writes deploy/GLOSS-tutorial-maintenance.pdf. Unlike the participant handout
this contains no passwords, so it is safe to share with collaborators.
"""
import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from make_handout import CSS, find_chrome  # noqa: E402  (shared styling)

REPO = "https://github.com/UbiWell/GLOSS.git"
BRANCH = "tutorial-deployment"


def build_html(host: str, port: str, admin: str) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<h1>GLOSS tutorial &mdash; maintaining the server</h1>
<p class="sub">How to push code changes to the ten participant instances, and
what to do when something breaks. Contains no passwords.</p>

<h2>What you need to know first</h2>
<p>The two Docker images contain <strong>no application code</strong> &mdash; the
Dockerfile copies only <code>environment_linux.yml</code>. Each participant's
code lives in <code>/srv/gloss/pNN</code> on the host and is bind-mounted into
their container at the same path.</p>
<div class="note"><strong>So a code change needs no image rebuild and no
container restart.</strong> Copy the files in and they are live. Only a change
to <code>environment_linux.yml</code> requires a rebuild.</div>

<h2>Layout</h2>
<pre>~/gloss-repo          a git clone of the {BRANCH} branch  (pull here)
~/gloss-clean         an rsync target, if you push from a laptop instead
/srv/gloss/_template  the golden copy all instances are synced from
/srv/gloss/p01..p10   one independent checkout per participant
/srv/gloss/_backups   files overwritten by an update, timestamped
/srv/gloss/images-backup.tgz   saved images, for disaster recovery</pre>

<h2>Workflow A &mdash; a collaborator pushes via GitHub (recommended)</h2>
<p>Your collaborator clones the repo, commits to the branch, and pushes as
normal:</p>
<pre>git clone -b {BRANCH} {REPO}
# ...edit, commit...
git push origin {BRANCH}</pre>

<p>Then on the server, pull and distribute:</p>
<pre>ssh -p {port} {admin}@{host}
cd ~/gloss-repo
git pull

# See what would change, without touching anything:
sudo bash deploy/update_instances.sh

# Distribute to all ten instances:
sudo bash deploy/update_instances.sh --apply</pre>

<p>The dry run prints a per-participant list of the files that would change, so
you can check the blast radius before applying. Changes take effect for the
next query a participant runs; nothing needs restarting.</p>

<h2>Workflow B &mdash; push straight from your laptop</h2>
<p>Useful for work that is not committed yet. Run from your local checkout:</p>
<pre>rsync -az --delete \\
  --exclude '.git' --exclude '__pycache__' --exclude 'sample_data_old' \\
  --exclude 'deploy/participants.txt' \\
  --exclude 'deploy/GLOSS-tutorial-logins.*' \\
  -e 'ssh -p {port}' \\
  ./ {admin}@{host}:~/gloss-clean/

ssh -p {port} {admin}@{host} \\
  'cd ~/gloss-clean &amp;&amp; sudo bash deploy/update_instances.sh --apply'</pre>
<div class="note">Always exclude <code>deploy/participants.txt</code>. It holds
every participant's password; overwriting it with a stale copy would break
logins, and committing it would publish them.</div>

<h2>What the update does and does not touch</h2>
<ul>
  <li>A participant's edit to a file that <em>also</em> changed upstream is
      overwritten, with the old version kept in
      <code>/srv/gloss/_backups/pNN-&lt;timestamp&gt;/</code>.</li>
  <li>Files a participant created that do not exist upstream are left alone,
      unless you pass <code>--force</code>.</li>
  <li>Ownership is reset to the participant's uid <em>inside</em> the container
      (not the host account's uid), so their files stay editable.</li>
  <li>Credentials, generated handouts, <code>code_generation.py</code> and other
      run artifacts are never distributed.</li>
</ul>

<h2>When you must rebuild (environment changes only)</h2>
<p>If <code>environment_linux.yml</code> changes, run the full provisioner. It
rebuilds both images and recreates all ten containers, which takes roughly
30 minutes on a cold cache and <strong>kills any session in progress</strong>:</p>
<pre>cd ~/gloss-repo
sudo -E env GATEWAY_API_KEY="$GATEWAY_API_KEY" PARTICIPANTS=10 \\
  bash deploy/provision.sh</pre>
<p>Passwords are preserved: the script reuses whatever is already in
<code>deploy/participants.txt</code>. Run it from a directory that <em>has</em>
that file, or it will generate new ones and invalidate your handout.</p>

<h2>Reset one participant</h2>
<p>For someone who has broken their copy. Takes about two seconds and does not
disturb the other nine or require a restart:</p>
<pre>sudo rsync -a --delete /srv/gloss/_template/ /srv/gloss/p03/
sudo chown -R 1000:1000 /srv/gloss/p03</pre>
<p>If they have broken the <em>container</em> rather than the code:</p>
<pre>sudo docker restart gloss-p03</pre>

<h2>Checking on things</h2>
<pre>sudo docker ps --filter name=gloss-p            # all ten should say "Up"
sudo docker logs gloss-p03 --tail 20            # why an instance won't start
sudo bash deploy/verify.sh                      # fast checks on every instance
sudo FULL=1 bash deploy/verify.sh               # ...plus a real query each (slow)
sudo systemctl list-timers gloss-janitor.timer  # container cleanup timer
df -h /                                         # disk</pre>

<h2>Things that will bite you</h2>
<ul>
  <li><strong>Never run <code>docker system prune -a</code>.</strong> The
      executor image exists only on this host; pruning it breaks code generation
      for everyone at once, with a misleading "pull access denied" error.
      Recover with
      <code>sudo docker load &lt; /srv/gloss/images-backup.tgz</code>.</li>
  <li><strong>Ports 22001&ndash;22010 are blocked</strong> by the provider's
      firewall. Participants connect on port {port} as <code>pNN</code>; their
      login shell drops them into their container. The published ports are only
      reachable from the host itself, which is what the browser-UI tunnel uses.</li>
  <li><strong>The model gateway allowlists this server's IP.</strong> If every
      instance suddenly fails at ACTION PLAN GENERATION, check it first:
      <code>curl -s -o /dev/null -w '%{{http_code}}' -H "Authorization: Bearer
      $GATEWAY_API_KEY" https://compute-gateway.europa.khoury.northeastern.edu/api/tags</code>.
      An HTML 403 means the allowlisting lapsed; nothing local will fix it.</li>
  <li><strong>Participants have effective root on the host</strong> via the
      mounted Docker socket. That was a deliberate trade for simplicity: keep
      nothing sensitive here and tear the server down afterwards.</li>
</ul>

<h2>Reprinting the participant handout</h2>
<p>After any change to credentials or instructions:</p>
<pre>python3 deploy/make_handout.py --host {host} --port {port}</pre>
<p>That writes <code>deploy/GLOSS-tutorial-logins.pdf</code>, which contains all
ten passwords &mdash; do not commit it or circulate it beyond the handout.</p>

</body></html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", default="65173")
    parser.add_argument("--admin", default="tutorial")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    out = pathlib.Path(args.out) if args.out else here / "GLOSS-tutorial-maintenance.pdf"

    html_path = out.with_suffix(".html")
    html_path.write_text(build_html(args.host, args.port, args.admin))

    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome/Chromium not found; the HTML is at " + str(html_path))

    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out}", html_path.as_uri()],
        check=True, capture_output=True,
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
