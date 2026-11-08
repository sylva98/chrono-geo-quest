import asyncio, pathlib, sys
from playwright.async_api import async_playwright

ROOT = pathlib.Path(__file__).resolve().parent
URL = (ROOT / "dist/index.html").as_uri()
SHOT = ROOT / "shots"
SHOT.mkdir(exist_ok=True)


def find_chrome():
    for p in ("/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome"):
        if pathlib.Path(p).exists():
            return p
    sys.exit("未找到 Chromium")


CHROME = find_chrome()


async def boot(page):
    await page.goto(URL)
    await page.wait_for_function("() => Array.isArray(QUESTIONS) && QUESTIONS.length > 0", timeout=20000)
    await page.wait_for_timeout(500)
    await page.click("#btnStart")
    await page.wait_for_timeout(400)
    await page.click('.sub-card[data-id="geo"]')
    await page.wait_for_timeout(500)
    await page.click("#btnEnter")
    await page.wait_for_timeout(700)


async def answer(page, right=False):
    idx = await page.evaluate("""(right) => {
        const q = S.queue[S.qi];
        if(!right) return (q.a + 1) % 4;
        return q.a;
    }""", right)
    await page.locator(".opt").nth(idx).click()
    await page.wait_for_timeout(500)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=CHROME)
        page = await browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        await boot(page)

        # ---------- 场景一：错一题 → 不退出，可继续，最终不进不退 ----------
        await page.evaluate("() => { S.era = 10; S.cores = 2; applyEra(10); startTravel(); }")
        await page.wait_for_timeout(600)
        st = await page.evaluate("() => ({mode:S.mode, wrong:S.travelWrong, total:S.levelTotal})")
        assert st == {"mode": "travel", "wrong": 0, "total": 6}, st

        await answer(page, right=False)
        st = await page.evaluate("""() => ({
            mode:S.mode, screen:document.querySelector('.screen.active')?.id,
            wrong:S.travelWrong, btn:$('btnNext').textContent,
            head:$('fbHead').textContent, fb:$('feedback').classList.contains('show')
        })""")
        print("第一次答错:", st)
        assert st["mode"] == "travel" and st["wrong"] == 1, st
        assert st["fb"] and st["btn"] == "继续深入", st
        await page.screenshot(path=str(SHOT / "rift-flow-1-hurt.png"))

        # 剩余 5 题全对 → 不进不退，核心保留
        await page.click("#btnNext")
        await page.wait_for_timeout(500)
        for _ in range(5):
            await answer(page, right=True)
            await page.wait_for_timeout(900)
        await page.wait_for_timeout(5200)
        st = await page.evaluate("""() => ({
            era:S.era, screen:document.querySelector('.screen.active')?.id,
            title:$('resTitle').textContent, sub:$('resSub').textContent,
            acc:$('resAcc').textContent, cores:S.cores
        })""")
        print("一错五对结算:", st)
        assert st["screen"] == "s-result" and st["era"] == 10, st
        assert st["title"] == "穿越未果" and "仍留在" in st["sub"], st
        assert st["cores"] == 2, st
        assert st["acc"].startswith("5 / 6"), st
        await page.screenshot(path=str(SHOT / "rift-flow-2-hold.png"))

        # ---------- 场景二：连错两题 → 当场崩裂，连退两级 ----------
        await page.evaluate("() => { S.era = 10; applyEra(10); startTravel(); }")
        await page.wait_for_timeout(600)
        await answer(page, right=False)
        await page.click("#btnNext")
        await page.wait_for_timeout(500)
        await answer(page, right=False)
        st = await page.evaluate("""() => ({
            mode:S.mode, wrong:S.travelWrong, btn:$('btnNext').textContent,
            head:$('fbHead').textContent, fb:$('feedback').classList.contains('show'),
            pips:document.querySelectorAll('.rift-pip.fill').length,
            lab:document.querySelector('.rift-lab')?.textContent
        })""")
        print("第二次答错:", st)
        assert st["wrong"] == 2 and st["fb"], st
        assert st["btn"] == "坠出裂隙" and st["pips"] == 2 and st["lab"] == "崩裂", st
        await page.screenshot(path=str(SHOT / "rift-flow-3-break.png"))

        await page.click("#btnNext")
        await page.wait_for_timeout(5200)
        st = await page.evaluate("""() => ({
            era:S.era, screen:document.querySelector('.screen.active')?.id,
            sub:$('resSub').textContent, acc:$('resAcc').textContent
        })""")
        print("两错结算:", st)
        assert st["screen"] == "s-result" and st["era"] == 8, st
        assert "连坠两级" in st["sub"], st
        assert st["acc"].startswith("0 / 2"), st
        await page.screenshot(path=str(SHOT / "rift-flow-4-fall2.png"))

        print("errors:", errs)
        assert not errs, errs
        await browser.close()
        print("OK")


asyncio.run(main())
