import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# 광주상무 극장 코드
THEATER_CODE = "0193"

EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")

TARGET_HALL = "1관"


def send_email(subject, body):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())


def iframe_url(date_yyyymmdd):
    return (
        "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
        f"?theatercode={THEATER_CODE}&date={date_yyyymmdd}"
    )


def fetch_html(date_yyyymmdd):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cgv.co.kr/",
    }
    r = requests.get(iframe_url(date_yyyymmdd), headers=headers, timeout=15)
    r.raise_for_status()
    return r.text


def has_schedule(html):
    return "상영시간표가 없습니다" not in html


def find_farthest_date(max_days=7):
    today = datetime.now()
    last_html = None
    last_date = None

    for i in range(max_days + 1):
        d = today + timedelta(days=i)
        ymd = d.strftime("%Y%m%d")

        try:
            html = fetch_html(ymd)
        except Exception:
            continue

        if has_schedule(html):
            last_html = html
            last_date = ymd

    return last_date, last_html


def parse_1gwan(html):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)

    lines = [ln for ln in text.split("\n") if TARGET_HALL in ln]

    blacklist = {"예매", "관람", "좌석", "잔여", "상영", "시간표", "전체", "CGV", "선택"}

    titles = []
    for ln in lines:
        for match in re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9 :\-\(\)·'’!,\.]{1,80}", ln):
            m = match.strip(" -:,.")
            if len(m) < 2:
                continue
            if any(b in m for b in blacklist):
                continue
            if m not in titles:
                titles.append(m)

    return titles, lines[:20]


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[CGV 광주상무 1관] 자동 체크 ({today})"

    far_date, html = find_farthest_date()

    if not html:
        body = "상영시간표 HTML을 가져오지 못했습니다."
        send_email(subject, body)
        return

    movies, debug_lines = parse_1gwan(html)

    body = f"기준일(가장 마지막으로 열린 날짜): {far_date}\n"
    body += "대상: 광주상무 1관\n\n"

    if movies:
        body += "상영작:\n"
        for m in movies:
            body += f"- {m}\n"
    else:
        body += "1관 파싱 실패\n\n디버그:\n"
        for l in debug_lines:
            body += l + "\n"

    send_email(subject, body)


if __name__ == "__main__":
    main()
