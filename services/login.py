import random
from playwright.async_api import Page


async def naver_login(page: Page, user_id: str, user_pw: str, log_callback=None) -> bool:
    """Playwright로 네이버 로그인을 수행한다."""

    async def log(msg: str):
        if log_callback:
            await log_callback(msg)

    try:
        await page.goto("https://nid.naver.com/nidlogin.login")
        await page.wait_for_timeout(int(random.uniform(1500, 2500)))

        # 이미 로그인 상태인지 확인
        if "nid.naver.com" not in page.url:
            await log("이미 로그인되어 있습니다. 로그인 과정을 건너뜁니다.")
            return True

        await log("로그인을 시도합니다...")

        if not user_pw:
            await log("비밀번호가 없어 자동 로그인을 할 수 없습니다.")
            return False

        # 클립보드 붙여넣기 방식으로 봇 감지 우회
        # ID 입력
        id_input = page.locator("#id")
        await id_input.click()
        await page.evaluate(
            """(id) => {
                document.querySelector('#id').value = id;
                document.querySelector('#id').dispatchEvent(new Event('input', {bubbles: true}));
            }""",
            user_id,
        )
        await page.wait_for_timeout(int(random.uniform(500, 1000)))

        # PW 입력
        pw_input = page.locator("#pw")
        await pw_input.click()
        await page.evaluate(
            """(pw) => {
                document.querySelector('#pw').value = pw;
                document.querySelector('#pw').dispatchEvent(new Event('input', {bubbles: true}));
            }""",
            user_pw,
        )
        await page.wait_for_timeout(int(random.uniform(500, 1000)))

        # 로그인 버튼 클릭
        await page.locator("#log\\.login").click()

        await log("로그인 처리 대기 중... (캡차가 발생하면 실패할 수 있습니다)")

        # 로그인 완료 대기 (최대 30초)
        max_wait = 30
        waited = 0
        while "nidlogin.login" in page.url or "step2" in page.url:
            await page.wait_for_timeout(1000)
            waited += 1
            if waited % 10 == 0:
                await log(f"로그인 완료 대기 중... ({waited}초 경과)")
            if waited > max_wait:
                await log("로그인 시간 초과 (30초).")
                return False

        await log("로그인 성공!")
        return True

    except Exception as e:
        await log(f"로그인 중 오류 발생: {e}")
        return False
