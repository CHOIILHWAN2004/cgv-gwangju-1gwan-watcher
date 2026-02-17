import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

from playwright.sync_api import sync_playwright

CGV_URL = "https://cgv.co.kr/cnm/movieBook/cinema"
THEATER_NAME = "광주상무"
TARGET_HALL = "1관"

EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def fetch_text():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(CGV_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)
        text = page.inner_text("body")
        browser.close()
    return text

def parse_movies_for_hall(text):
    lines = [ln.strip() for ln in text.split("\n") if TARGET_HALL in ln]
    joined = " ".join(lines)

    candidates = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9 :\-\(\)·'’!,\.]{1,60}", joined)

    blacklist = {"예매", "상영시간표", "관람", "좌석", "극장", "CGV", "로그인", "확인"}
    movies = []
    for c in candidates:
        c = c.strip(" -:,.")
        if len(c) < 2:
            continue
        if any(b in c for b in blacklist):
            continue
        movies.append(c)

    uniq = []
    for m in movies:
        if m not in uniq and len(m) <= 60:
            uniq.append(m)

    return uniq[:20]

def send_email(subject, body):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

def main():
    text = fetch_text()
    movies = parse_movies_for_hall(text)

    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[CGV 광주상무 1관] 스케줄 체크 ({today})"
    body = "\n".join(f"- {m}" for m in movies) if movies else "1관 상영작 추출 실패"

    send_email(subject, body)

if __name__ == "__main__":
    main()
