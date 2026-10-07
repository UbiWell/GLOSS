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
    # One login command per participant, with the tunnel already in it. There
    # used to be two -- a plain terminal login and a second one for the
    # dashboard -- and two ways in meant two sets of instructions and people
    # lost between them. The dashboard is the only way participants use GLOSS,
    # so the command that reaches it is the only one printed.
    table_rows = "\n".join(
        f'      <tr><td class="mono">{html.escape(r["user"])}</td>'
        f'<td class="mono">{html.escape(r["password"])}</td>'
        f'<td class="mono">ssh -p {html.escape(port)} '
        f'-L 8501:127.0.0.1:{html.escape(r["uiport"] or "8501")} '
        f'{html.escape(r["user"])}@{html.escape(host)}</td></tr>'
        for r in rows
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>{CSS}</style></head><body>

<h1>GLOSS hands-on tutorial</h1>
<p class="sub">Each participant has their own private copy of GLOSS on a shared
server. Nothing you do affects anyone else.</p>

<h2>1. Connect</h2>
<p>Open a terminal and run the command from your row in the table at the end.
It is complete as printed &mdash; nothing to substitute. Enter your password when
prompted; <strong>it will not appear on screen as you type</strong>, which is
normal.</p>
<pre>ssh -p {html.escape(port)} -L 8501:127.0.0.1:&lt;your UI port&gt; p01@{html.escape(host)}</pre>
<p>The first time, it will ask you to accept the host key: type
<code>yes</code>. You will land directly inside your own GLOSS instance. There
is nothing to install or activate.</p>

<h2>2. Start the dashboard</h2>
<p>In that same window, run:</p>
<pre>streamlit run sensemaking_ui.py</pre>
<p>Wait for <code>You can now view your Streamlit app in your browser</code>,
then open this address in your own browser:</p>
<pre>http://localhost:8501</pre>
<p><strong>Leave the terminal window open</strong> while you use the dashboard
&mdash; closing it stops the dashboard. Press <code>Ctrl-C</code> there when you
are done.</p>

<h2>3. Ask a question</h2>
<p>Everything happens in the left-hand sidebar:</p>
<ul>
  <li><strong>Question</strong> &mdash; type one, or click one of the examples below the box</li>
  <li><strong>How should the answer be presented?</strong> &mdash; for example
      <code>clear and concise</code>, or <code>three bullet points</code></li>
  <li>Press <strong>Run</strong></li>
</ul>
<p>Both boxes need something in them, or <strong>Run</strong> stays greyed out.
The second one matters more than it looks: the same evidence presented two ways
gives two quite different answers.</p>

<div class="note"><strong>Always say who and when.</strong> Put the user id
(<code>user1</code>) and a date or date range in every question. GLOSS assumes
no default for either, so <em>how many texts were sent?</em> has nothing to look
up &mdash; <em>how many texts did user1 send on 2020-11-02?</em> does.</div>

<div class="note"><strong>The CODE GENERATION stage prints nothing while it
runs.</strong> Several minutes of silence there is normal &mdash; it is not stuck.</div>

<p>Results fill in across four tabs: <strong>Overview</strong>,
<strong>Agent graph</strong>, <strong>Agent activity</strong> and
<strong>Generated code</strong>. The last two are worth a look &mdash; they show
what each agent said, and the Python it wrote and ran.</p>

<h2>4. What you can ask about</h2>
<p>The user id in this dataset is always <code>user1</code>, and the data runs
from 2019 to 2022. <code>2020-11-02</code> is a well-populated day to start
from. These databases are available:</p>
<ul>
  <li><strong>sms</strong> &mdash; message metadata: direction, length, read status, contact</li>
  <li><strong>call log</strong> &mdash; incoming, outgoing and missed calls with durations</li>
  <li><strong>app usage</strong> &mdash; which app was in the foreground over time</li>
  <li><strong>lock unlock</strong> &mdash; when the phone was locked and unlocked</li>
  <li><strong>sensing mobility</strong> &mdash; where they were and how they moved:
      distance, places visited, time at home and other places, activity</li>
</ul>
<p>You never say which database to use. Part of what GLOSS does is work that
out &mdash; the <strong>Overview</strong> tab shows which one it chose.</p>

<h2>5. If something goes wrong</h2>
<ul>
  <li><strong>The browser will not load the page.</strong> Check the dashboard is
      still running in your terminal window.</li>
  <li><strong>ssh said <code>bind: Address already in use</code>.</strong> Something
      on your own machine is using port 8501. Reconnect with
      <code>-L 8601:127.0.0.1:&lt;your UI port&gt;</code> and open
      <code>http://localhost:8601</code> instead.</li>
  <li><strong>A run seems stuck.</strong> Press <strong>Stop</strong> in the sidebar
      and run it again.</li>
  <li><strong>Errors mentioning the gateway.</strong> The shared language model is
      busy or unreachable &mdash; tell the organiser rather than retrying repeatedly.</li>
  <li><strong>Your connection dropped.</strong> Connect again and restart the
      dashboard.</li>
  <li>Please do not run <code>docker</code> commands &mdash; you do not need them,
      and they affect the other participants.</li>
</ul>

<h2>Credentials</h2>
<table>
  <tr><th>You are</th><th>Password</th><th>Your login command</th></tr>
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
