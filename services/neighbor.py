import random
from playwright.async_api import Page


async def add_neighbor(page: Page, blog_url: str, message: str, log_callback=None) -> str:
    """블로그를 방문하여 서로이웃 신청을 수행한다."""

    async def log(msg: str):
        if log_callback:
            await log_callback(msg)

    try:
        # 네이버 블로그 URL 검증
        if "blog.naver.com" not in blog_url:
            return "Skipped (Not Naver Blog)"

        parts = blog_url.split("/")
        if len(parts) < 4:
            return "Invalid URL"

        blog_id = parts[3]

        # 1. 블로그 메인 방문
        main_blog_url = f"https://blog.naver.com/{blog_id}"
        await page.goto(main_blog_url)
        await page.wait_for_timeout(2000)

        # 2. 이웃추가 버튼 찾기
        button_clicked = False

        # 메인 페이지에서 버튼 찾기
        button_selectors = [
            "a:has-text('이웃추가')",
            "a.btn_add",
            "a.btn_neighbor",
            "span:has-text('이웃추가') >> xpath=..",
        ]

        for selector in button_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.is_visible(timeout=1000):
                    await btn.click()
                    button_clicked = True
                    break
            except Exception:
                continue

        # mainFrame 내부에서도 시도
        if not button_clicked:
            try:
                frame = page.frame("mainFrame")
                if frame:
                    for selector in button_selectors:
                        try:
                            btn = frame.locator(selector).first
                            if await btn.is_visible(timeout=1000):
                                await btn.click()
                                button_clicked = True
                                break
                        except Exception:
                            continue
            except Exception:
                pass

        # 3. 버튼 못 찾으면 직접 URL로 이동
        if button_clicked:
            await page.wait_for_timeout(2000)
            # 새 팝업 창이 열렸는지 확인
            pages = page.context.pages
            if len(pages) > 1:
                popup = pages[-1]
            else:
                button_clicked = False

        if not button_clicked:
            pc_add_url = f"https://blog.naver.com/BuddyAdd.naver?blogId={blog_id}"
            # 새 탭이 아닌 현재 작업용 페이지에서 이동
            popup = page
            await popup.goto(pc_add_url)
            await popup.wait_for_timeout(1000)

        # 4. 서로이웃 신청 페이지 처리
        try:
            # alert 확인
            popup.on("dialog", lambda dialog: dialog.accept())

            body_text = await popup.locator("body").text_content() or ""

            # 이미 서로이웃
            if "님과 현재 서로이웃입니다" in body_text or "서로이웃을 이웃으로 변경" in body_text:
                await _close_popup(popup, page)
                return "Already Mutual Neighbor"

            # 이미 이웃
            if "이웃인 블로그입니다" in body_text:
                await _close_popup(popup, page)
                return "Already Neighbor"

            # STEP 1: 서로이웃 라디오 버튼 선택
            radio_buttons = await popup.locator("input[type='radio']").all()

            if len(radio_buttons) >= 2:
                await radio_buttons[1].click(force=True)
                await popup.wait_for_timeout(300)
            elif len(radio_buttons) <= 1:
                # 서로이웃 옵션 없음 - ID로 재시도
                mutual_found = False
                for rid in ["each_buddy", "bothBuddyRadio"]:
                    try:
                        el = popup.locator(f"#{rid}")
                        if await el.count() > 0:
                            await el.click(force=True)
                            mutual_found = True
                            break
                    except Exception:
                        continue

                if not mutual_found:
                    await _close_popup(popup, page)
                    return "Only Neighbor Available"

            # 다음 버튼 클릭
            try:
                next_btn = popup.locator("a.btn_ok, a.button_next, a[href='#next']").first
                await next_btn.click()
            except Exception:
                next_btn = popup.locator("a:has-text('다음')").first
                await next_btn.click()

            await popup.wait_for_timeout(1000)

            # STEP 2: 메시지 입력
            msg_input = None
            msg_selectors = ["#message", "textarea", "input[name='message']", "input[name='buddyMemo']", "input[name='memo']"]

            for sel in msg_selectors:
                try:
                    loc = popup.locator(sel).first
                    if await loc.is_visible(timeout=3000):
                        msg_input = loc
                        break
                except Exception:
                    continue

            if msg_input is None:
                await _close_popup(popup, page)
                return "Failed at Message Step"

            # 기존 텍스트 지우고 새 메시지 입력
            await msg_input.click()
            await msg_input.press("Control+a")
            await msg_input.press("Delete")
            await popup.evaluate(
                """([sel, msg]) => {
                    const el = document.querySelector(sel);
                    if (el) {
                        el.value = msg;
                        el.innerText = msg;
                        el.dispatchEvent(new Event('input', {bubbles: true}));
                        el.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                }""",
                [await _get_selector(msg_input), message],
            )
            await popup.wait_for_timeout(500)

            # 다음 버튼 클릭
            try:
                next_btn2 = popup.locator("a.btn_ok, a.button_next").first
                await next_btn2.click()
            except Exception:
                next_btn2 = popup.locator("a:has-text('다음')").first
                await next_btn2.click()

            await popup.wait_for_timeout(1000)

            # STEP 3: 닫기
            try:
                close_btn = popup.locator("a:has-text('닫기')").first
                await close_btn.click(timeout=2000)
            except Exception:
                pass

            await _close_popup(popup, page)
            return "Success"

        except Exception as e:
            error_msg = str(e)
            if "제한" in error_msg or "초과" in error_msg:
                await _close_popup(popup, page)
                return "Limit Exceeded"
            await _close_popup(popup, page)
            return f"Failed in Popup"

    except Exception as e:
        return "Error"


async def _close_popup(popup: Page, main_page: Page):
    """팝업 페이지를 닫고 메인 페이지로 돌아간다."""
    try:
        if popup != main_page and not popup.is_closed():
            await popup.close()
    except Exception:
        pass


async def _get_selector(locator) -> str:
    """locator에서 CSS 셀렉터를 추출하기 위한 헬퍼. 실패 시 기본값 반환."""
    # Playwright locator에서 직접 selector를 얻기 어려우므로 fallback
    return "#message, textarea, input[name='message'], input[name='buddyMemo']"
