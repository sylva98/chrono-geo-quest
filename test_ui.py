import asyncio, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path("/Users/a123/WorkBuddy/2026-11-06-16-24-47")
URL = (ROOT / "dist/index.html").as_uri()
SHOT = ROOT / "shots"
SHOT.mkdir(exist_ok=True, parents=True)
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        await page.goto(URL)
        await page.wait_for_timeout(900)
        await page.screenshot(path=str(SHOT / "1-title.png"))

        await page.click("#btnStart")
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(SHOT / "2-brief.png"))

        await page.click("#btnEnter")
        await page.wait_for_timeout(900)
        await page.screenshot(path=str(SHOT / "3-question-stone.png"))

        # 答对一题
        correct = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth(correct).click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT / "4-correct.png"))

        # 答错一题 → 无核心 → 坠落转场
        await page.click("#btnNext")
        await page.wait_for_timeout(300)
        n = await page.locator(".opt").count()
        correct = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth((correct + 1) % n).click()
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(SHOT / "5-wrong.png"))
        await page.click("#btnNext")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT / "6-transit.png"))
        await page.wait_for_timeout(900)
        await page.screenshot(path=str(SHOT / "7-fallen-glacier.png"))

        # 各时代氛围抽样（直接切换渲染）
        for era in [5, 8, 13, 15, 20]:
            await page.evaluate(f"applyEra({era}); S.era={era}; renderRail();")
            await page.evaluate("renderQuestion()")
            await page.wait_for_timeout(1600)
            name = (await page.evaluate("ERAS[S.era].n")).replace(" ", "")
            await page.screenshot(path=str(SHOT / f"mood-{era}.png"))
            print("shot era", era, name)

        print("console errors:", errs)
        print("state:", await page.evaluate("({era:S.era,cores:S.cores,total:S.total})"))
        await browser.close()

asyncio.run(main())
