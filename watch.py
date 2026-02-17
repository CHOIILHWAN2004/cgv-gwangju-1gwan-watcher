import os
import re
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText

import requests
from bs4 import BeautifulSoup

# ✅ 광주/전라/제주 areacode = 206 (참고 자료 기반)  :contentReference[oaicite:2]{index=2}
AREACODE = "206"
THEATER_CODE = "0193"  # 광주상무 (당신이 확인한 코드)

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


def iframe_url(date_yyyymmdd: str) -> str:
    # areacode 포함 + 일부 구현체에서 쓰는 빈 파라미터까지 같이 붙여 “정상 HTML” 확률 올림 :contentReference[oaicite:3]{index=3}
    base = "https://www.cgv.co.kr/common/showtimes/iframeTheater.aspx"
    return (
        f"{base}?areacode={AREACODE}"
        f"&theatercode={THEATER_CODE}"
        f"&date={date_yyyymmdd}"
        f"&screencodes=&screenratingcode=&regioncode="
    )


def fetch_html(date_yyyymmdd: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cgv.co.kr/",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }
    r = requests.get(iframe_url(date_yyyymmdd), headers=headers, timeout=20)
    r.raise_for_status()
    return r.text


def has_schedule(html: str) -> bool:
    # 일부 날짜는 "상영시간표가 없습니다"가 뜸 :contentReference[oaicite:4]{index=4}
    return ("상영시간표가 없습니다" not in html) and (len(html.strip()) > 200)


def find_farthest_date(max_days_ahead=10):
    today = datetime.now()
    last_date = None
    last_html = None

    for i in range(max_days_ahead + 1):
        d = today + timedelta(days=i)
        ymd = d.strftime("%Y%m%d")
        try:
            html = fetch_html(ymd)
        except Exception:
            continue

        if has_schedule(html):
            last_date = ymd
            last_html = html

    return last_date, last_html


def parse_1gwan(html: str):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)

    # 1관이 포함된 줄
    lines = [ln for ln in text.split("\n") if TARGET_HALL in ln]

    # 제목 후보 뽑기(단순/보수적으로)
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

    return titles, lines[:25]


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[CGV 광주상무 1관] 자동 체크 ({today})"

    far_date, html = find_farthest_date(max_days_ahead=10)

    if not html:
        body = "상영시간표 HTML을 가져오지 못했습니다.\n"
        body += f"(요청 URL 예시: {iframe_url(datetime.now().strftime('%Y%m%d'))})\n"
        send_email(subject, body)
        return

    movies, debug_lines = parse_1gwan(html)

    body = f"기준일(가장 마지막으로 열린 날짜): {far_date}\n대상: 광주상무 1관\n\n"

    if movies:
        body += "상영작 후보:\n" + "\n".join(f"- {m}" for m in movies)
    else:
        body += "1관 파싱 실패\n\n디버그(1관 포함 라인 일부):\n"
        body += "\n".join(debug_lines) if debug_lines else "(1관 라인 자체가 없음)"

    send_email(subject, body)


if __name__ == "__main__":
    main()
