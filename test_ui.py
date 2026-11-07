import asyncio, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
URL = (ROOT / "dist/index.html").as_uri()
SHOT = ROOT / "shots"
SHOT.mkdir(exist_ok=True, parents=True)
import shutil, sys

def find_chrome():
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"):
        if pathlib.Path(p).exists():
            return p
    print("未找到 Chromium/Chrome，请安装或修改 CHROME 变量", file=sys.stderr)
    sys.exit(1)

CHROME = find_chrome()


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=CHROME,
            args=["--autoplay-policy=no-user-gesture-required"],
        )
        page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))

        await page.goto(URL)
        await page.wait_for_timeout(700)
        await page.screenshot(path=str(SHOT / "t1-title.png"))

        # 科目选择
        await page.click("#btnStart")
        await page.wait_for_timeout(600)
        await page.screenshot(path=str(SHOT / "t2-subjects.png"))
        cards = await page.locator(".sub-card").count()
        print("subject cards:", cards)

        await page.click('.sub-card[data-id="hist"]')
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(SHOT / "t3-subject-hist.png"))
        print("brief kicker:", await page.inner_text("#briefKicker"))
        print("audio:", await page.evaluate("({ctx: !!Sfx.ctx, state: Sfx.ctx && Sfx.ctx.state, music: !!Music.timer, era: Music.era})"))

        await page.click("#btnEnter")
        await page.wait_for_timeout(900)
        print("hudSub:", await page.inner_text("#hudSub"))
        await page.screenshot(path=str(SHOT / "t4-question-hist.png"))

        # 答对 → 自动跳题 + 音效
        q0 = await page.evaluate("S.qi")
        a = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth(a).click()
        await page.wait_for_timeout(400)
        await page.screenshot(path=str(SHOT / "t5-correct.png"))
        await page.wait_for_timeout(900)
        print("auto advance:", q0, "->", await page.evaluate("S.qi"))

        # 答错 → 核心提示
        await page.evaluate("S.cores=2; renderHud();")
        n = await page.locator(".opt").count()
        a = await page.evaluate("S.queue[S.qi].a")
        await page.locator(".opt").nth((a + 1) % n).click()
        await page.wait_for_timeout(500)
        print("core btn visible:", await page.is_visible("#btnCore"))
        await page.screenshot(path=str(SHOT / "t6-wrong.png"))

        # 音乐随纪元切换
        for era in [5, 15, 20]:
            await page.evaluate(f"applyEra({era}); S.era={era}; Music.setEra({era});")
            await page.wait_for_timeout(700)
            print("era", era, "music cfg bpm", await page.evaluate("Music.cfg.bpm"),
                  "drone:", await page.evaluate("!!Music.drone"))
            await page.screenshot(path=str(SHOT / f"t7-era-{era}.png"))

        # 声音开关
        await page.click("#btnSnd")
        await page.wait_for_timeout(200)
        print("muted ->", await page.evaluate("Sfx.on"), "music timer:", await page.evaluate("!!Music.timer"))
        await page.click("#btnSnd")
        await page.wait_for_timeout(300)
        print("unmuted ->", await page.evaluate("Sfx.on"), "music timer:", await page.evaluate("!!Music.timer"))

        # 混合模式抽题
        await page.evaluate("newGame('mix'); S.sub")
        mix = await page.evaluate("bankFor('mix').length")
        print("mixed bank:", mix)
        hist = await page.evaluate("bankFor('hist').length")
        print("hist bank:", hist)

        print("console errors:", errs)
        await browser.close()

asyncio.run(main())
