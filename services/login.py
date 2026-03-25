import json
from playwright.async_api import BrowserContext


async def naver_login_with_cookies(context: BrowserContext, cookies_json: str, log_callback=None) -> bool:
    """쿠키를 사용하여 네이버에 로그인한다."""

    async def log(msg: str):
        if log_callback:
            await log_callback(msg)

    try:
        cookies = json.loads(cookies_json)

        # 쿠키를 Playwright 형식으로 변환
        pw_cookies = []
        for cookie in cookies:
            pw_cookie = {
                "name": cookie.get("name", ""),
                "value": cookie.get("value", ""),
                "domain": cookie.get("domain", ".naver.com"),
                "path": cookie.get("path", "/"),
            }
            if cookie.get("expirationDate"):
                pw_cookie["expires"] = cookie["expirationDate"]
            pw_cookies.append(pw_cookie)

        await context.add_cookies(pw_cookies)
        await log(f"쿠키 {len(pw_cookies)}개를 적용했습니다.")

        # 로그인 확인
        page = await context.new_page()
        await page.goto("https://www.naver.com")
        await page.wait_for_timeout(2000)

        # 로그인 상태 확인 (네이버 메인에서 로그인 버튼 유무)
        login_btn = page.locator("a.MyView-module__link_login___HpHMW")
        if await login_btn.count() > 0:
            await log("쿠키 로그인 실패. 쿠키가 만료되었거나 잘못되었습니다.")
            await page.close()
            return False

        await log("쿠키 로그인 성공!")
        await page.close()
        return True

    except json.JSONDecodeError:
        await log("쿠키 형식이 올바르지 않습니다. JSON 형식으로 입력해주세요.")
        return False
    except Exception as e:
        await log(f"로그인 중 오류 발생: {e}")
        return False
