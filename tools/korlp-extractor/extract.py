#!/usr/bin/env python3
"""
korlp.org 게시글 추출기 (Playwright 기반)

회원 로그인이 필요한 대한이비인후과의사회(korlp.org) 게시판 페이지를
로그인 세션으로 열어 본문을 추출한다. 로그인하지 않으면 alert 팝업이
뜨고 본문이 비어 나오는 페이지를 다루기 위해, 다이얼로그(alert/confirm)를
가로채 텍스트를 기록하고, 로그인 폼 필드를 자동 감지한다.

사용법:
    1) pip install -r requirements.txt
    2) playwright install chromium
    3) .env.example 를 .env 로 복사하고 본인 계정 정보를 채운다
    4) python extract.py
       또는 특정 URL 지정: python extract.py "https://www.korlp.org/html/?pmode=BBBS0028900025"

출력:
    - 콘솔에 추출된 본문 텍스트
    - output/ 디렉터리에 rendered.html, content.txt, screenshot.png 저장
"""

import os
import re
import sys
import pathlib
from datetime import datetime

try:
    from dotenv import load_dotenv
except ImportError:
    print("python-dotenv 가 필요합니다: pip install -r requirements.txt", file=sys.stderr)
    raise

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("playwright 가 필요합니다: pip install -r requirements.txt && playwright install chromium",
          file=sys.stderr)
    raise


BASE = "https://www.korlp.org"
HERE = pathlib.Path(__file__).resolve().parent
OUTDIR = HERE / "output"

load_dotenv(HERE / ".env")

KORLP_ID = os.getenv("KORLP_ID", "").strip()
KORLP_PW = os.getenv("KORLP_PW", "").strip()
LOGIN_URL = os.getenv("KORLP_LOGIN_URL", f"{BASE}/html/?pmode=login").strip()
TARGET_URL = os.getenv("KORLP_TARGET_URL", f"{BASE}/html/?pmode=BBBS0028900025").strip()
HEADLESS = os.getenv("KORLP_HEADLESS", "true").strip().lower() not in ("0", "false", "no")

# 필드 자동 감지가 실패할 때 .env 로 직접 지정할 수 있는 셀렉터(선택).
ID_SELECTOR = os.getenv("KORLP_ID_SELECTOR", "").strip()
PW_SELECTOR = os.getenv("KORLP_PW_SELECTOR", "").strip()
SUBMIT_SELECTOR = os.getenv("KORLP_SUBMIT_SELECTOR", "").strip()

# ID 입력 칸으로 자주 쓰이는 name/id 후보 (한국형 BBS 관례).
ID_CANDIDATES = [
    "input[name='mb_id']", "input[name='user_id']", "input[name='userid']",
    "input[name='id']", "input[name='login_id']", "input[name='m_id']",
    "input[name='memId']", "input[name='loginId']", "input[id='mb_id']",
    "input[id='user_id']", "input[id='id']", "input[id='loginId']",
]


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")


def find_first(page, selectors):
    for sel in selectors:
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                return el, sel
        except Exception:
            continue
    return None, None


def detect_login_fields(page):
    """로그인 폼의 ID/PW/제출 요소를 감지한다."""
    # 비밀번호 칸: type=password 가 가장 신뢰할 수 있는 단서.
    pw_el = None
    pw_sel = PW_SELECTOR
    if PW_SELECTOR:
        pw_el = page.query_selector(PW_SELECTOR)
    if not pw_el:
        for cand in page.query_selector_all("input[type='password']"):
            if cand.is_visible():
                pw_el = cand
                pw_sel = "input[type='password']"
                break

    # ID 칸: 명시 셀렉터 → 후보 목록 → 비밀번호 칸 직전의 text 입력칸.
    id_el = None
    id_sel = ID_SELECTOR
    if ID_SELECTOR:
        id_el = page.query_selector(ID_SELECTOR)
    if not id_el:
        id_el, id_sel = find_first(page, ID_CANDIDATES)
    if not id_el:
        texts = [c for c in page.query_selector_all(
            "input[type='text'], input:not([type])") if c.is_visible()]
        if texts:
            id_el = texts[0]
            id_sel = "first visible text input"

    return id_el, id_sel, pw_el, pw_sel


def do_login(page):
    if not KORLP_ID or not KORLP_PW:
        log("경고: KORLP_ID / KORLP_PW 가 .env 에 설정되지 않았습니다. 로그인 없이 진행합니다.")
        return False

    log(f"로그인 페이지 이동: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    id_el, id_sel, pw_el, pw_sel = detect_login_fields(page)
    if not id_el or not pw_el:
        log("로그인 폼 필드를 자동 감지하지 못했습니다.")
        log("브라우저 개발자도구로 ID/PW input 의 name 또는 id 를 확인한 뒤,")
        log(".env 에 KORLP_ID_SELECTOR / KORLP_PW_SELECTOR / KORLP_SUBMIT_SELECTOR 를 지정하세요.")
        return False

    log(f"ID 필드 감지: {id_sel}")
    log(f"PW 필드 감지: {pw_sel}")
    id_el.fill(KORLP_ID)
    pw_el.fill(KORLP_PW)

    # 제출: 명시 셀렉터 → 흔한 제출 버튼 → Enter.
    submitted = False
    submit_candidates = [SUBMIT_SELECTOR] if SUBMIT_SELECTOR else [
        "input[type='submit']", "button[type='submit']",
        "button:has-text('로그인')", "a:has-text('로그인')",
        "input[value='로그인']", "img[alt='로그인']",
    ]
    for sel in submit_candidates:
        if not sel:
            continue
        try:
            el = page.query_selector(sel)
            if el and el.is_visible():
                log(f"제출 버튼 클릭: {sel}")
                el.click()
                submitted = True
                break
        except Exception:
            continue
    if not submitted:
        log("제출 버튼을 찾지 못해 Enter 키로 제출합니다.")
        pw_el.press("Enter")

    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PWTimeout:
        pass
    page.wait_for_timeout(1500)

    # 로그인 성공 추정: '로그아웃' 링크 존재 여부.
    logged_in = bool(page.query_selector("a:has-text('로그아웃'), :text('로그아웃')"))
    log(f"로그인 상태 추정: {'성공' if logged_in else '확인 불가(계속 진행)'}")
    return logged_in


# "내가 쓴 글" / 마이페이지 후보 경로 (사이트마다 메뉴명이 달라 여러 개 시도).
MY_POSTS_CANDIDATES = [
    "?pmode=my", "?pmode=my_info", "?pmode=scrap", "?pmode=searchComment",
]


def collect_post_links(page, url):
    """주어진 페이지에서 개별 글(smode=view&seq=...) 링크를 모아 반환한다.

    '내가 쓴 글' 같은 목록 페이지를 가리키면, 비활성화된 게시판 목록 주소
    대신 실제로 열 수 있는 개별 글의 정확한 주소(seq 포함)를 찾을 수 있다.
    """
    log(f"링크 수집 페이지 이동: {url}")
    page.goto(url, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PWTimeout:
        pass
    page.wait_for_timeout(1500)

    final_url = page.url
    redirected = "pmode=main" in final_url or final_url.rstrip("/").endswith("korlp.org")
    links = []
    seen = set()
    for a in page.query_selector_all("a[href*='seq=']"):
        href = a.get_attribute("href") or ""
        if "smode=view" not in href and "seq=" not in href:
            continue
        full = href if href.startswith("http") else f"{BASE}/html/{href.lstrip('/')}" \
            if not href.startswith("?") else f"{BASE}/html/{href}"
        if full in seen:
            continue
        seen.add(full)
        text = (a.inner_text() or "").strip().replace("\n", " ")
        links.append((text, full))
    return final_url, redirected, links


def extract_content(page):
    log(f"대상 페이지 이동: {TARGET_URL}")
    page.goto(TARGET_URL, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PWTimeout:
        pass
    page.wait_for_timeout(2000)

    final_url = page.url
    if "pmode=main" in final_url and "pmode=main" not in TARGET_URL:
        log(f"주의: 대상 주소가 메인 페이지로 리다이렉트되었습니다 ({final_url}).")
        log("게시판 목록 주소가 비활성화되었거나 접근 권한이 없을 수 있습니다.")
        log("개별 글은 '?pmode=...&smode=view&seq=번호' 형태의 주소로 열어보세요.")
        log("'내가 쓴 글' 목록에서 실제 주소를 찾으려면: python extract.py --links")

    title = page.title()
    html = page.content()

    # 본문 추정: 흔한 본문 컨테이너 우선, 없으면 body 전체.
    body_text = ""
    for sel in ["#bo_v_con", ".view_content", ".board_view", "#contents",
                "#content", ".content", "table", "body"]:
        el = page.query_selector(sel)
        if el:
            txt = (el.inner_text() or "").strip()
            if len(txt) > len(body_text):
                body_text = txt
        if sel in ("#bo_v_con", ".view_content", ".board_view") and body_text:
            break
    if not body_text:
        body_text = page.inner_text("body")

    body_text = re.sub(r"\n{3,}", "\n\n", body_text).strip()
    return title, html, body_text


def make_page(p, dialog_messages):
    browser = p.chromium.launch(headless=HEADLESS)
    context = browser.new_context(
        user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0 Safari/537.36"),
        locale="ko-KR",
    )
    page = context.new_page()

    # alert/confirm 팝업 가로채기: 텍스트 기록 후 닫기.
    def on_dialog(dialog):
        dialog_messages.append(dialog.message)
        log(f"팝업 감지({dialog.type}): {dialog.message}")
        try:
            dialog.accept()
        except Exception:
            try:
                dialog.dismiss()
            except Exception:
                pass
    page.on("dialog", on_dialog)
    return browser, page


def run_links_mode(list_url):
    """목록 페이지에서 개별 글의 실제 주소(seq 포함)를 찾아 출력한다."""
    dialog_messages = []
    with sync_playwright() as p:
        browser, page = make_page(p, dialog_messages)
        do_login(page)

        urls_to_try = [list_url] if list_url else MY_POSTS_CANDIDATES
        all_links = []
        for u in urls_to_try:
            full = u if u.startswith("http") else f"{BASE}/html/{u}"
            final_url, redirected, links = collect_post_links(page, full)
            tag = " (메인으로 리다이렉트됨)" if redirected else ""
            log(f"  → {full}{tag}: 글 링크 {len(links)}개")
            for t, l in links:
                all_links.append((u, t, l))
        browser.close()

    print("\n" + "=" * 70)
    print("발견한 개별 글 링크 (이 주소로 python extract.py \"<주소>\" 실행)")
    print("=" * 70)
    if not all_links:
        print("개별 글 링크를 찾지 못했습니다.")
        print("브라우저에서 '마이페이지 → 내가 쓴 글'을 직접 연 뒤,")
        print("'직원 명단' 글을 우클릭 → '링크 주소 복사'로 실제 주소를 얻어")
        print("python extract.py \"<복사한 주소>\" 로 실행하세요.")
        if dialog_messages:
            print("\n[팝업 메시지]")
            for m in dialog_messages:
                print(f"  - {m}")
    else:
        for src, text, link in all_links:
            label = text if text else "(제목 없음)"
            print(f"\n[{src}] {label}\n  {link}")
    print("\n" + "=" * 70)


def main():
    global TARGET_URL

    args = sys.argv[1:]
    if args and args[0] == "--links":
        run_links_mode(args[1].strip() if len(args) > 1 else "")
        return
    if args:
        TARGET_URL = args[0].strip()

    OUTDIR.mkdir(exist_ok=True)
    dialog_messages = []

    with sync_playwright() as p:
        browser, page = make_page(p, dialog_messages)

        do_login(page)
        title, html, body_text = extract_content(page)

        (OUTDIR / "rendered.html").write_text(html, encoding="utf-8")
        (OUTDIR / "content.txt").write_text(
            f"URL: {TARGET_URL}\nTITLE: {title}\n\n{body_text}\n", encoding="utf-8")
        try:
            page.screenshot(path=str(OUTDIR / "screenshot.png"), full_page=True)
        except Exception as e:
            log(f"스크린샷 실패: {e}")

        browser.close()

    print("\n" + "=" * 70)
    print(f"TITLE: {title}")
    print("=" * 70)
    if dialog_messages:
        print("\n[팝업 메시지]")
        for m in dialog_messages:
            print(f"  - {m}")
        print("\n위 팝업이 떴다면 로그인이 안 됐거나 권한이 없는 글일 수 있습니다.")
    print("\n[본문]\n")
    print(body_text if body_text else "(본문이 비어 있습니다 — 로그인/권한을 확인하세요)")
    print("\n" + "=" * 70)
    print(f"저장 위치: {OUTDIR}")
    print("  - rendered.html  (렌더링된 전체 HTML)")
    print("  - content.txt    (추출된 본문 텍스트)")
    print("  - screenshot.png (전체 페이지 스크린샷)")


if __name__ == "__main__":
    main()
