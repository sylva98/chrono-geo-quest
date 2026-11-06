import asyncio, pathlib
from playwright.async_api import async_playwright

ROOT = pathlib.Path("/Users/a123/WorkBuddy/2026-11-06-16-24-47")
URL = (ROOT / "dist/index.html").as_uri()
SHOT = ROOT / "shots"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

async def run(page, right, tag):
    await page.evaluate(f"""() => {{
        S.era = 10; S.travelFrom = 10; S.mode = 'travel';
        S.levelRight = {right}; S.levelTotal = 3; S.cores = 1;
        show('s-play'); renderHud();
        travelResult();
    }}""")
    await page.wait_for_timeout(900)
    await page.screenshot(path=str(SHOT / f"rift-{tag}-1spin.png"))
    await page.wait_for_timeout(1400)
    await page.screenshot(path=str(SHOT / f"rift-{tag}-2reveal.png"))
    await page.wait_for_timeout(1300)
    await page.screenshot(path=str(SHOT / f"rift-{tag}-3hold.png"))
    await page.wait_for_timeout(1600)
    await page.screenshot(path=str(SHOT / f"rift-{tag}-4result.png"))

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        await page.goto(URL)
        await page.wait_for_timeout(600)
        await page.click("#btnStart")
        await page.wait_for_timeout(500)
        await page.click("#btnEnter")
        await page.wait_for_timeout(700)

        await run(page, 3, "ascend")
        await run(page, 2, "fall")
        print("errors:", errs)
        await browser.close()

asyncio.run(main())
