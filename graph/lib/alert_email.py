"""Mechanical last-resort email for alert-watcher.sh: no model, no retries.

Credentials live in `smtp.env` beside this file (never committed):
    SMTP_HOST= SMTP_PORT= SMTP_USER= SMTP_PASS= SMTP_FROM= SMTP_TO=
This host has no mail transport and port 25 egress is blocked (checked
2026-08-31), so without that file the email cannot exist — the script then
says exactly that on stdout and exits 1 instead of pretending.
"""

from __future__ import annotations

import pathlib
import smtplib
import ssl
import sys
from email.message import EmailMessage

ENV = pathlib.Path(__file__).with_name("smtp.env")


def credentials() -> dict[str, str]:
    if not ENV.exists():
        raise SystemExit(f"email not sent: no SMTP credentials at {ENV} "
                         "(SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS/SMTP_FROM/SMTP_TO)")
    if ENV.stat().st_mode & 0o077:
        raise SystemExit(f"email not sent: {ENV} is readable by group or other — "
                         "it holds credentials; chmod 600 it")
    pairs = dict(line.split("=", 1) for line in ENV.read_text("utf-8").split()
                 if "=" in line)
    missing = [k for k in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASS", "SMTP_FROM", "SMTP_TO")
               if not pairs.get(k) or pairs[k] == "FILL_ME"]
    if missing:
        raise SystemExit(f"email not sent: {ENV} is missing {', '.join(missing)}")
    return pairs


def send(why: str, flags: str, important: bool = False) -> None:
    creds = credentials()
    to = creds["SMTP_TO"]
    message = EmailMessage()
    message["From"], message["To"] = creds["SMTP_FROM"], to
    message["Subject"] = ("IMPORTANT — graph campaign: a red flag has stood 15+ minutes"
                          if important else
                          "graph supervisor: red flags stand and WATCHER is unreachable")
    if important:
        message["X-Priority"] = "1"
        message["Importance"] = "high"
    message.set_content(f"{why}\n\nThe red flags:\n{flags}\n")
    port = int(creds["SMTP_PORT"])
    # 465 is implicit TLS from the first byte (one.com's send.one.com); 587 is
    # plain first, upgraded by STARTTLS. Certificates are verified either way.
    tls = ssl.create_default_context()
    server: smtplib.SMTP = (
        smtplib.SMTP_SSL(creds["SMTP_HOST"], port, timeout=30, context=tls)
        if port == 465 else smtplib.SMTP(creds["SMTP_HOST"], port, timeout=30))
    with server:
        if port != 465:
            server.starttls(context=tls)
        server.login(creds["SMTP_USER"], creds["SMTP_PASS"])
        server.send_message(message)
    print(f"alert email sent to {to}")


if __name__ == "__main__":
    why = sys.argv[1] if len(sys.argv) > 1 else "unknown error"
    check = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
    # the whole file: a byte cap silently dropped every warning after the first few
    send(why, check.read_text("utf-8") if check and check.exists() else "")
