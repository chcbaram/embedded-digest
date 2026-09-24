"""SMTP 메일 전달.

필요 환경변수: SMTP_HOST, SMTP_PORT(기본 587), SMTP_USER, SMTP_PASSWORD,
              MAIL_FROM(기본 SMTP_USER), MAIL_TO(쉼표 구분)
"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

NAME = "email"
REQUIRED = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "MAIL_TO"]


def available() -> tuple[bool, str]:
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    return (not missing, f"환경변수 누락: {', '.join(missing)}")


def _html(markdown_text: str) -> str:
    # 의존성을 늘리지 않으려고 최소한의 변환만 한다. 본문은 plain text 도 함께 보낸다.
    escaped = (markdown_text.replace("&", "&amp;")
               .replace("<", "&lt;").replace(">", "&gt;"))
    return ("<html><body style=\"font-family:-apple-system,sans-serif;"
            "line-height:1.6;max-width:720px\"><pre style=\"white-space:pre-wrap;"
            f"font-family:inherit\">{escaped}</pre></body></html>")


def send(subject: str, markdown: str, blocks: list[dict]) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("MAIL_FROM") or os.environ["SMTP_USER"]
    msg["To"] = os.environ["MAIL_TO"]
    msg.set_content(markdown)
    msg.add_alternative(_html(markdown), subtype="html")

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"])
        s.send_message(msg)
