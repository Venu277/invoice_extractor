import asyncio
from playwright.async_api import async_playwright

async def audit():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://127.0.0.1:8000/home")

        # Inject axe-core
        await page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.0/axe.min.js")
        results = await page.evaluate("axe.run()")
        violations = results.get("violations", [])
        passes = results.get("passes", [])
        print(f"Accessibility Passes: {len(passes)}")
        print(f"Accessibility Violations: {len(violations)}")
        for v in violations:
            print(f"- [{v.get('impact')}] {v.get('id')}: {v.get('description')}")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(audit())
