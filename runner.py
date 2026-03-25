"""
GitHub Actions에서 실행되는 standalone 자동화 러너.
실시간 로그를 GitHub Gist에 업데이트하여 프론트엔드에서 polling으로 확인.
"""
import asyncio
import json
import os
import random
import time
import urllib.request

from playwright.async_api import async_playwright

from services.login import naver_login
from services.search import search_blogs
from services.neighbor import add_neighbor


GIST_ID = os.environ.get("GIST_ID", "")
GH_TOKEN = os.environ.get("GH_TOKEN", "")

logs: list[str] = []
progress = {"tried": 0, "success": 0, "skipped": 0, "failed": 0}
status = "running"


def update_gist():
    """현재 상태를 GitHub Gist에 업데이트한다."""
    if not GIST_ID or not GH_TOKEN:
        return

    data = json.dumps({
        "status": status,
        "progress": progress,
        "logs": logs[-50:],  # 최근 50줄만
    }, ensure_ascii=False)

    body = json.dumps({
        "files": {
            "status.json": {"content": data}
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        data=body,
        method="PATCH",
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        print(f"Gist 업데이트 실패: {e}")


def delete_gist():
    """작업 완료 후 Gist를 삭제한다."""
    if not GIST_ID or not GH_TOKEN:
        return

    req = urllib.request.Request(
        f"https://api.github.com/gists/{GIST_ID}",
        method="DELETE",
        headers={
            "Authorization": f"Bearer {GH_TOKEN}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        print(f"Gist {GIST_ID} 삭제 완료")
    except Exception as e:
        print(f"Gist 삭제 실패: {e}")


async def log(msg: str):
    print(msg)
    logs.append(msg)
    # 10줄마다 Gist 업데이트 (API 호출 절약)
    if len(logs) % 10 == 0:
        update_gist()


async def main():
    global status, progress

    naver_id = os.environ.get("NAVER_ID", "")
    naver_pw = os.environ.get("NAVER_PW", "")
    keyword = os.environ.get("KEYWORD", "")
    message = os.environ.get("MESSAGE", "")
    max_count = int(os.environ.get("MAX_COUNT", "100"))

    if not naver_id or not keyword or not message:
        await log("필수 환경변수가 누락되었습니다.")
        status = "error"
        update_gist()
        save_result()
        return

    await log(f"[{keyword}] 키워드로 최대 {max_count}명에게 신청을 시작합니다.")
    update_gist()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-gpu", "--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )

        page = await context.new_page()

        # 1. 로그인
        if not await naver_login(page, naver_id, naver_pw, log_callback=log):
            await log("로그인 실패.")
            status = "error"
            update_gist()
            save_result()
            await browser.close()
            return
        await log("로그인 확인 완료. 2초 후 검색을 시작합니다...")
        await page.wait_for_timeout(2000)

        # 2. 검색 & 신청 루프
        page_num = 1
        started_at = time.time()

        while progress["success"] < max_count:
            if time.time() - started_at > 1800:  # 30분 타임아웃
                await log("작업 시간 초과로 자동 종료됩니다.")
                break

            await log(f"\n[페이지 {page_num}] 검색 중...")
            blog_urls = await search_blogs(page, keyword, max_count=10, page_num=page_num, log_callback=log)

            if not blog_urls:
                await log("더 이상 검색 결과가 없습니다.")
                break

            for url in blog_urls:
                if progress["success"] >= max_count:
                    break

                progress["tried"] += 1
                await log(f"[{progress['tried']}] 방문 중: {url}...")
                result = await add_neighbor(page, url, message, log_callback=log)

                if result == "Success":
                    progress["success"] += 1
                    await log(f" -> ✅ 신청 성공! (진행: {progress['success']}/{max_count})")
                elif result == "Limit Exceeded":
                    await log(" -> ⛔ 일일 신청 한도를 초과했습니다.")
                    break
                else:
                    progress["skipped"] += 1
                    labels = {
                        "Already Mutual Neighbor": "이미 서로이웃임",
                        "Only Neighbor Available": "이웃추가만 가능 (건너뜀)",
                        "Already Neighbor": "이미 신청됨/이웃임",
                        "Failed in Popup": "팝업 창 처리 실패",
                        "Skipped (Not Naver Blog)": "네이버 블로그 아님",
                    }
                    await log(f" -> ⏭️ {labels.get(result, result)}")

                delay = random.uniform(1.5, 2.5)
                await page.wait_for_timeout(int(delay * 1000))

            if progress["success"] >= max_count:
                break

            page_num += 1
            if page_num > 100:
                await log("검색 한계 보호 임계치 도달.")
                break

        await browser.close()

    duration = int(time.time() - started_at)
    status = "completed"
    await log(f"\n작업 완료! (성공: {progress['success']}건, 소요: {duration}초)")
    update_gist()
    save_result()

    # 완료 후 60초 대기 (마지막 polling 보장) → Gist 삭제
    await log("60초 후 상태 데이터가 자동 삭제됩니다.")
    update_gist()
    await asyncio.sleep(60)
    delete_gist()


def save_result():
    """결과를 JSON 파일로 저장한다."""
    with open("result.json", "w", encoding="utf-8") as f:
        json.dump({
            "status": status,
            "progress": progress,
            "logs": logs,
        }, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
