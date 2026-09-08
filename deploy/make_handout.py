#!/usr/bin/env python3
"""
Build the participant handout PDF from deploy/participants.txt.

Renders HTML then prints it to PDF with headless Chrome, so there is no LaTeX or
wkhtmltopdf dependency.

    python3 deploy/make_handout.py --host 207.56.9.25 --port 65173

Writes deploy/GLOSS-tutorial-logins.pdf. The credentials table is one row per
participant, so a single page can be printed and cut into slips.
"""
import argparse
import html
import pathlib
import shutil
import subprocess
import sys

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
]

CSS = """
@page { size: A4; margin: 16mm 14mm; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
       color: #1a1a1a; font-size: 10.5pt; line-height: 1.45; }
h1 { font-size: 19pt; margin: 0 0 2mm; }
h2 { font-size: 12.5pt; margin: 7mm 0 2mm; padding-bottom: 1mm;
     border-bottom: 1px solid #d8d8d8; }
.sub { color: #555; margin: 0 0 5mm; }
code, pre { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 9.5pt; }
pre { background: #f5f5f5; border-left: 3px solid #b9b9b9;
      padding: 2.5mm 3mm; margin: 2mm 0; white-space: pre-wrap; }
table { border-collapse: collapse; width: 100%; margin-top: 2mm; }
th, td { border: 1px solid #ccc; padding: 1.8mm 2.5mm; text-align: left; }
th { background: #efefef; font-size: 9.5pt; }
td.mono { font-family: "SF Mono", Menlo, Consolas, monospace; }
.note { background: #fbf7e8; border-left: 3px solid #d8b34a;
        padding: 2.5mm 3mm; margin: 3mm 0; }
ol, ul { margin: 2mm 0 2mm 5mm; padding: 0; }
li { margin-bottom: 1.2mm; }
.footer { margin-top: 6mm; color: #666; font-size: 9pt; }
"""


def read_participants(path: pathlib.Path):
    """Parse participants.txt.

    The password is always the last column; the UI port is the third when
    present. Written this way so the older 3-column file still parses.
    """
    rows = []
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) < 3 or parts[0] == "user":
            continue
        rows.append({
            "user": parts[0],
            "password": parts[-1],
            "uiport": parts[2] if len(parts) >= 4 else "",
        })
    return rows


def build_html(rows, host: str, port: str) -> str:
    table_rows = "\n".join(
        f'      <tr><td class="mono">{html.escape(r["user"])}</td>'
        f'<td class="mono">{html.escape(r["password"])}</td>'
        f'<td class="mono">ssh -p {html.escape(port)} {html.escape(r["user"])}@{html.escape(host)}</td>'
        f'<td class="mono">ssh -p {html.escape(port)} -L 8501:localhost:{html.escape(r["uiport"] or "8501")} '
        f'{html.escape(r["user"])}@{html.escape(host)}</td></tr>'
        for r in rows
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<h1>GLOSS hands-on tutorial</h1>
<p class="sub">Each participant has their own private copy of GLOSS on a shared
server. You can edit the code freely: nothing you do affects anyone else.</p>

<h2>1. Log in</h2>
<p>Open a terminal and run the command from your row in the table below,
substituting nothing &mdash; it is complete as printed. Enter your password when
prompted (it will not appear on screen as you type).</p>
<pre>ssh -p {html.escape(port)} p01@{html.escape(host)}</pre>
<p>You will land directly inside your own GLOSS instance, in your copy of the
code. There is nothing to install or activate.</p>

<h2>2. Run your first query</h2>
<pre>python sensemaking_process.py</pre>
<p>This runs the full sensemaking pipeline and prints every stage: the action
plan, the databases it chooses, the code it generates, and the final answer.
Expect it to take a few minutes.</p>

<div class="note"><strong>The CODE GENERATION stage prints nothing while it
runs.</strong> Several minutes of silence there is normal &mdash; it is not stuck.</div>

<h2>3. Ask your own question</h2>
<p>Open <code>sensemaking_process.py</code>, scroll to the bottom, and edit the
<code>query</code> string. Then run it again.</p>
<pre>query = '''
on nov 2 2020, for user1 how many text messages were sent and received?'''</pre>
<p>The user id in this dataset is always <code>user1</code>. Five databases are
available:</p>
<ul>
  <li><strong>sms</strong> &mdash; message metadata: direction, length, read status, contact</li>
  <li><strong>call log</strong> &mdash; incoming, outgoing and missed calls with durations</li>
  <li><strong>app usage</strong> &mdash; which app was in the foreground over time</li>
  <li><strong>lock unlock</strong> &mdash; when the phone was locked and unlocked</li>
  <li><strong>sensing</strong> &mdash; daily aggregates: activity, audio, conversations, time at places</li>
</ul>
<p>Data runs from 2019 to 2022. <code>2020-11-02</code> is a well-populated day
to start from.</p>

<h2>4. Useful commands</h2>
<pre>python -m agents.local_model     # check your connection to the language model
python sensemaking_process.py    # run a query
exit                             # log out</pre>

<h2>5. Optional: use the graphical interface in your browser</h2>
<p>GLOSS also has a dashboard that shows each stage of the pipeline as it runs.
It runs on the server, so you reach it through your SSH connection rather than
by opening a public address. It takes two steps.</p>

<p><strong>Step 1.</strong> Log out if you are already connected, then reconnect
using the <em>Browser UI login</em> command from your row in the table. It is the
same login with a tunnel added:</p>
<pre>ssh -p {port} -L 8501:localhost:&lt;your UI port&gt; p01@{host}</pre>

<p><strong>Step 2.</strong> In that session, start the dashboard:</p>
<pre>streamlit run sensemaking_ui.py</pre>

<p>Then open this address in your own browser:</p>
<pre>http://localhost:8501</pre>

<p>Type your query in the box and press <strong>Start Sense-Making</strong>. The
expanders fill in as each agent finishes. Leave the terminal window open while
you use it &mdash; closing it stops the dashboard. Press <code>Ctrl-C</code> in the
terminal when you are done.</p>

<div class="note"><strong>Avoid the &ldquo;Open in New Tab&rdquo; buttons</strong> in the
dashboard. They try to open a browser on the server rather than on your machine,
so they do nothing useful here. Everything you need is on the main page.</div>

<h2>6. If something goes wrong</h2>
<ul>
  <li><strong>A run seems stuck.</strong> Press <code>Ctrl-C</code> and run it again.</li>
  <li><strong>Errors mentioning the gateway.</strong> The shared language model is
      busy or unreachable &mdash; tell the organiser rather than retrying repeatedly.</li>
  <li><strong>You broke your copy of the code.</strong> Ask the organiser; your
      instance can be reset in seconds without affecting anyone else.</li>
  <li>Please do not run <code>docker</code> commands &mdash; you do not need them,
      and they affect the other participants.</li>
</ul>

<h2>Credentials</h2>
<table>
  <tr><th>You are</th><th>Password</th><th>Terminal login (section 1)</th><th>Browser UI login (section 5)</th></tr>
{table_rows}
</table>

<p class="footer">Passwords are specific to this session and stop working when the
server is shut down after the tutorial.</p>

</body></html>
"""


def find_chrome():
    for candidate in CHROME_CANDIDATES:
        if candidate.startswith("/"):
            if pathlib.Path(candidate).exists():
                return candidate
        elif shutil.which(candidate):
            return shutil.which(candidate)
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", default="65173")
    parser.add_argument("--creds", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    here = pathlib.Path(__file__).resolve().parent
    creds = pathlib.Path(args.creds) if args.creds else here / "participants.txt"
    out = pathlib.Path(args.out) if args.out else here / "GLOSS-tutorial-logins.pdf"

    if not creds.exists():
        sys.exit(f"credentials file not found: {creds}")
    rows = read_participants(creds)
    if not rows:
        sys.exit(f"no participants parsed from {creds}")

    html_path = out.with_suffix(".html")
    html_path.write_text(build_html(rows, args.host, args.port))

    chrome = find_chrome()
    if not chrome:
        sys.exit("Chrome/Chromium not found; the HTML is at " + str(html_path))

    subprocess.run(
        [chrome, "--headless", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={out}", html_path.as_uri()],
        check=True, capture_output=True,
    )
    print(f"wrote {out} ({len(rows)} participants)")


if __name__ == "__main__":
    main()
