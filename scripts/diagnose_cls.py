import asyncio
import subprocess
import time
import requests
from playwright.async_api import async_playwright

async def diagnose():
    server_process = None
    try:
        requests.get("http://127.0.0.1:8000/health", timeout=1)
    except Exception:
        server_process = subprocess.Popen(
            [r".\venv\Scripts\python.exe", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        for _ in range(15):
            time.sleep(0.5)
            try:
                if requests.get("http://127.0.0.1:8000/health", timeout=1).status_code == 200:
                    break
            except Exception:
                pass

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        await page.add_init_script("""
            new PerformanceObserver((entryList) => {
                for (const entry of entryList.getEntries()) {
                    if (!entry.hadRecentInput) {
                        for (const source of entry.sources) {
                            console.log('LAYOUT SHIFT val:', entry.value, 'node:', source.node ? source.node.nodeName : 'null', 'class:', source.node ? source.node.className : '', 'prev:', JSON.stringify(source.previousRect), 'curr:', JSON.stringify(source.currentRect));
                        }
                    }
                }
            }).observe({type: 'layout-shift', buffered: true});
        """)

        page.on("console", lambda msg: print(msg.text) if 'LAYOUT SHIFT' in msg.text else None)

        await page.goto("http://127.0.0.1:8000/home")
        await page.wait_for_timeout(1000)

        for scroll_y in [400, 900, 1500, 2200, 3000]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(400)

        await browser.close()

    if server_process:
        server_process.terminate()

if __name__ == '__main__':
    asyncio.run(diagnose())
