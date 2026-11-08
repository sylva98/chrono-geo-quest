import asyncio, pathlib, sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
URL = (ROOT / "dist/index.html").as_uri()
SHOT = ROOT / "shots"
SHOT.mkdir(exist_ok=True, parents=True)

def find_chrome():
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if pathlib.Path(p).exists():
            return p
    sys.exit(1)

CHROME = find_chrome()

async def snap(page, name):
    await page.screenshot(path=str(SHOT / f"egg-{name}.png"))
    print("shot:", name)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        await page.goto(URL)
        await page.wait_for_function("() => Array.isArray(QUESTIONS) && QUESTIONS.length > 0", timeout=20000)
        await page.wait_for_timeout(600)

        for cyc in (0, 1, 2):
            # —— 最高境界结算屏 ——
            # beginRun 会按进度自动判周目，所以先开局再把周目掰回目标值
            await page.evaluate(f"""() => {{
                beginRun(SUBJECTS[0].id);
                CYCLE = {cyc}; TM = CYCLES[CYCLE]; ERAS = TM.eras;
                document.documentElement.dataset.cycle = String(CYCLE);
                S.era = MAX_ERA; S.correct = 21; S.total = 26;
                S.travels = 2; S.travelWins = 1; S.t0 = Date.now() - 754000;
                applyEra(S.era);
                winGame();
            }}""")
            await page.wait_for_timeout(2600)
            dc = await page.evaluate("document.documentElement.dataset.cycle")
            print("win cycle attr =", dc)
            await snap(page, f"win-c{cyc}")
            await page.click("#winSigil")
            await page.wait_for_timeout(700)
            await snap(page, f"win-c{cyc}-egg")

            # —— 最低谷底结算屏 ——
            await page.evaluate(f"""() => {{
                beginRun(SUBJECTS[0].id);
                CYCLE = {cyc}; TM = CYCLES[CYCLE]; ERAS = TM.eras;
                document.documentElement.dataset.cycle = String(CYCLE);
                S.era = 0; S.correct = 0; S.total = 4;
                S.t0 = Date.now() - 120000;
                applyEra(S.era);
                gameOver();
            }}""")
            await page.wait_for_timeout(2400)
            dc = await page.evaluate("document.documentElement.dataset.cycle")
            print("over cycle attr =", dc)
            await snap(page, f"over-c{cyc}")
            await page.click("#overSpark")
            await page.wait_for_timeout(900)
            await snap(page, f"over-c{cyc}-egg")

        print("JS errors:", errs if errs else "none")
        await browser.close()

asyncio.run(main())
