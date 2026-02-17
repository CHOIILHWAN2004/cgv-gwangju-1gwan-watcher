import os
import re
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CGV_URL = "https://cgv.co.kr/cnm/movieBook/cinema"
THEATER_NAME = "광주상무"
TARGET_HALL = "1관"

EMAIL_TO = os.getenv("EMAIL_TO")
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def send_email(subject, body):
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_FROM, EMAIL_PASS)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())

def fetch_1gwan_block_text():
    """
    1) 예매 페이지 진입
    2) 극장 선택 UI에서 '광주상무' 클릭
    3) 날짜 리스트에서 '가장 마지막 날짜' 클릭
    4) 페이지 텍스트에서 '1관'이 포함된 줄들을 수집
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.goto(CGV_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 팝업/배너 등으로 클릭 막힐 수 있어 스크롤 한 번
        page.mouse.wheel(0, 600)
        page.wait_for_timeout(500)

        # 1) 극장 선택 버튼(텍스트 기반) 클릭 시도
        clicked = False
        for label in ["극장", "극장선택", "극장 선택", "극장별"]:
            try:
                page.get_by_text(label, exact=False).first.click(timeout=1500)
                clicked = True
                break
            except Exception:
                continue

        # 못 찾으면 그냥 진행(페이지 UI가 바뀐 케이스)
        page.wait_for_timeout(800)

        # 2) 극장명 클릭
        try:
            page.get_by_text(THEATER_NAME, exact=False).click(timeout=8000)
        except PWTimeout:
            # 목록이 안 열렸을 수도 있어 다시 한 번 '극장'쪽 클릭 후 재시도
            try:
                page.get_by_text("극장", exact=False).first.click(timeout=1500)
                page.wait_for_timeout(800)
                page.get_by_text(THEATER_NAME, exact=False).click(timeout=8000)
            except Exception:
                pass

        page.wait_for_timeout(1500)

        # 3) 날짜 탭 중 "마지막" 클릭 (요일이 들어간 요소 기준)
        # 요일(월화수목금토일)이 포함된 버튼/탭들을 찾아 마지막 요소 클릭
        try:
            date_candidates = page.locator("button, a, li").filter(
                has_text=re.compile(r"(월|화|수|목|금|토|일)")
            )
            n = date_candidates.count()
            if n > 0:
                date_candidates.nth(n - 1).click()
                page.wait_for_timeout(1200)
        except Exception:
            pass

        # 4) 최종 텍스트 수집
        text = page.inner_text("body")
        browser.close()

    # 5) '1관' 포함된 줄 수집
    lines = [ln.strip() for ln in text.split("\n") if TARGET_HALL in ln]
    lines = [ln for ln in lines if ln]
    return lines

def parse_movie_titles(lines):
    # '1관' 줄들에서 제목 후보만 뽑아 정리
    joined = " ".join(lines)

    # 제목 후보 패턴 (너무 공격적으로 안 함)
    candidates = re.findall(r"[가-힣A-Za-z0-9][가-힣A-Za-z0-9 :\-\(\)·'’!,\.]{1,60}", joined)

    blacklist = {"예매", "상영시간표", "관람", "좌석", "극장", "CGV", "로그인", "확인", "일반", "청소년", "성인"}
    movies = []
    for c in candidates:
        c = c.strip(" -:,.")
        if len(c) < 2:
            continue
        if any(b in c for b in blacklist):
            continue
        movies.append(c)

    # 중복 제거
    uniq = []
    for m in movies:
        if m not in uniq:
            uniq.append(m)
    return uniq[:15]

def def main():
    today = datetime.now().strftime("%Y-%m-%d")
    subject = f"[DEBUG] CGV 광주상무 HTML 체크 ({today})"

    farthest_ymd, html = find_farthest_date(max_days_ahead=5)

    if not html:
        body = "HTML 자체를 못 받아옴"
        send_email(subject, body)
        return

    body = "=== HTML 일부 ===\n\n"
    body += html[:2000]  # 앞 2000자만
    send_email(subject, body)

if __name__ == "__main__":
    main()
