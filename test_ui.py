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

        # 确认时代条带已移除
        strip = await page.evaluate("!!document.getElementById('rail')")
        print("rail exists:", strip)

        # 答对 → 应自动进入下一题（无需点按钮）
        q0 = await page.evaluate("S.qi")
        correct = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth(correct).click()
        await page.wait_for_timeout(380)
        await page.screenshot(path=str(SHOT / "4-correct-toast.png"))
        await page.wait_for_timeout(1000)
        q1 = await page.evaluate("S.qi")
        fb_open = await page.evaluate("document.getElementById('feedback').classList.contains('show')")
        print(f"auto-advance: qi {q0} -> {q1}, feedback panel open = {fb_open}")
        await page.screenshot(path=str(SHOT / "5-autonext.png"))

        # 答错 → 有核心：出现「使用冷冻核心」选项
        await page.evaluate("S.cores=2; renderHud();")
        n = await page.locator(".opt").count()
        correct = await page.evaluate("S.queue[S.qi].a")
        qi_before = await page.evaluate("S.qi")
        await page.locator(".opt").nth((correct + 1) % n).click()
        await page.wait_for_timeout(600)
        core_visible = await page.is_visible("#btnCore")
        print("core button visible:", core_visible, "| text:", await page.inner_text("#btnCore"))
        await page.screenshot(path=str(SHOT / "6-wrong-core.png"))

        # 使用核心 → 换新题重答，核心 -1
        await page.click("#btnCore")
        await page.wait_for_timeout(700)
        print("after core:", await page.evaluate("({cores:S.cores, qi:S.qi, total:S.total})"))
        await page.screenshot(path=str(SHOT / "7-core-used.png"))

        # 无核心时答错 → 直接坠落
        await page.evaluate("S.cores=0; renderHud();")
        n = await page.locator(".opt").count()
        correct = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth((correct + 1) % n).click()
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT / "8-wrong-nocore.png"))
        await page.click("#btnNext")
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(SHOT / "9-transit.png"))
        await page.wait_for_timeout(2000)
        await page.screenshot(path=str(SHOT / "10-fallen-glacier.png"))

        # 各时代氛围抽样
        for era in [5, 8, 13, 15, 20]:
            await page.evaluate(f"applyEra({era}); S.era={era}; renderRail();")
            await page.evaluate("renderQuestion()")
            await page.wait_for_timeout(1600)
            name = (await page.evaluate("ERAS[S.era].n")).replace(" ", "")
            await page.screenshot(path=str(SHOT / f"mood-{era}.png"))
            print("shot era", era, name)

        print("console errors:", errs)
        print("state:", await page.evaluate("({era:S.era,cores:S.cores,total:S.total,qi:S.qi})"))
        await browser.close()

asyncio.run(main())
