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

        for cyc, eras in ((0, [20]), (1, [0, 5, 13, 20]), (2, [0, 9, 20])):
            await page.evaluate(f"""() => {{
                localStorage.clear();
                beginRun(SUBJECTS[0].id);
                CYCLE = {cyc}; TM = CYCLES[CYCLE]; ERAS = TM.eras;
                document.documentElement.dataset.cycle = String(CYCLE);
            }}""")
            for era in eras:
                await page.evaluate(f"""() => {{
                    S.era = {era}; applyEra(S.era); Music.setEra(S.era);
                    enterEra();
                }}""")
                await page.wait_for_timeout(2400)
                cfg = await page.evaluate("Music.cfg")
                nm = await page.evaluate(f"ERAS[{era}].n")
                mood = await page.evaluate(f"ERAS[{era}].mood")
                print(f"c{cyc} era{era}", nm, mood, "bpm", cfg['bpm'], "cut", cfg['cut'], "dens", cfg['dens'])
                await page.screenshot(path=str(SHOT / f"quiz-c{cyc}-e{era}.png"))

        print("JS errors:", errs if errs else "none")
        await browser.close()

asyncio.run(main())
