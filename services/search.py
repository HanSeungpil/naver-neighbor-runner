import random
from playwright.async_api import Page


async def search_blogs(page: Page, keyword: str, max_count: int = 10, page_num: int = 1, log_callback=None) -> list[str]:
    """네이버 블로그 섹션에서 키워드로 검색하여 블로그 URL 목록을 반환한다."""

    async def log(msg: str):
        if log_callback:
            await log_callback(msg)

    blog_urls: list[str] = []

    try:
        url = (
            f"https://section.blog.naver.com/Search/Post.naver"
            f"?pageNo={page_num}&rangeType=ALL&orderBy=sim&keyword={keyword}"
        )
        await page.goto(url)
        await page.wait_for_timeout(int(random.uniform(1500, 2000)))

        # 포스트 링크 수집
        links = await page.locator("a.desc_inner").all()

        if not links:
            links = await page.locator("div.list_search_post .desc a").all()

        if not links:
            await log("이 페이지에서 검색 결과를 찾지 못했습니다.")
            return []

        for link in links:
            href = await link.get_attribute("href")
            if href and "blog.naver.com" in href:
                blog_urls.append(href)

        await log(f"페이지 {page_num}에서 {len(blog_urls)}개의 블로그를 발견했습니다.")

    except Exception as e:
        await log(f"검색 중 오류: {e}")

    return blog_urls
