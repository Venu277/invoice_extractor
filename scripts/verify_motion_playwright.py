import asyncio
import os
import subprocess
import time
import requests
from playwright.async_api import async_playwright

async def verify_homepage():
    # 1. Start uvicorn server in background if not already running
    server_process = None
    try:
        requests.get("http://127.0.0.1:8000/health", timeout=1)
        print("Server already running on http://127.0.0.1:8000")
    except Exception:
        print("Starting uvicorn server...")
        server_process = subprocess.Popen(
            [r".\venv\Scripts\python.exe", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        for _ in range(15):
            time.sleep(0.5)
            try:
                r = requests.get("http://127.0.0.1:8000/health", timeout=1)
                if r.status_code == 200:
                    print("Server successfully ready!")
                    break
            except Exception:
                pass

    os.makedirs("docs/screenshots", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()

        # TEST A: JavaScript DISABLED
        print("\n--- TEST A: JavaScript Disabled ---")
        no_js_context = await browser.new_context(java_script_enabled=False)
        no_js_page = await no_js_context.new_page()
        await no_js_page.goto("http://127.0.0.1:8000/home")
        
        # Verify content is fully visible
        h1_vis = await no_js_page.is_visible("h1")
        assert h1_vis, "H1 must be visible without JS"
        about_text_vis = await no_js_page.is_visible("#about")
        assert about_text_vis, "About section must be visible without JS"
        await no_js_page.screenshot(path="docs/screenshots/home_no_js.png")
        print("PASS: No-JS fallback verified. Screenshot saved to docs/screenshots/home_no_js.png")
        await no_js_context.close()

        # TEST B: prefers-reduced-motion: reduce
        print("\n--- TEST B: Reduced Motion Mode ---")
        reduced_context = await browser.new_context(reduced_motion="reduce")
        reduced_page = await reduced_context.new_page()
        await reduced_page.goto("http://127.0.0.1:8000/home")
        await reduced_page.wait_for_timeout(500)
        
        # Typewriter text should be completely visible immediately
        tw_text = await reduced_page.eval_on_selector("[data-typewriter]", "el => el.textContent")
        assert "Axion turns the invoices" in tw_text, f"Reduced motion should have full text immediately, got: {tw_text[:50]}"
        await reduced_page.screenshot(path="docs/screenshots/home_reduced_motion.png")
        print("PASS: Reduced motion verified. Screenshot saved to docs/screenshots/home_reduced_motion.png")
        await reduced_context.close()

        # TEST C: Interactive Normal Motion & Scrolling
        print("\n--- TEST C: Interactive Normal Mode ---")
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # Track CLS (Cumulative Layout Shift)
        await page.add_init_script("""
            window.__cls = 0;
            new PerformanceObserver((entryList) => {
                for (const entry of entryList.getEntries()) {
                    if (!entry.hadRecentInput) {
                        window.__cls += entry.value;
                    }
                }
            }).observe({type: 'layout-shift', buffered: true});
        """)

        await page.goto("http://127.0.0.1:8000/home")
        await page.wait_for_timeout(800)

        # Scroll in steps to trigger reveals
        for scroll_y in [400, 900, 1500, 2200, 3000]:
            await page.evaluate(f"window.scrollTo(0, {scroll_y})")
            await page.wait_for_timeout(350)

        await page.wait_for_timeout(1000)

        # Check all [data-reveal] elements ended at opacity 1
        reveals = await page.query_selector_all("[data-reveal]")
        for i, rev in enumerate(reveals):
            op = await rev.evaluate("el => window.getComputedStyle(el).opacity")
            assert float(op) >= 0.95, f"Reveal element #{i} did not end at opacity 1 (got {op})"

        # Check typewriter text completed and matches source text
        source_text = await page.eval_on_selector("[data-typewriter]", "el => el.dataset.typewriterText || el.textContent")
        rendered_chars = await page.eval_on_selector_all(".typewriter-char.is-typed", "els => els.length")
        print(f"Typewriter typed {rendered_chars} characters (source length {len(source_text)})")
        assert rendered_chars > 0, "Typewriter should have typed characters"

        # Check CLS < 0.02
        cls_score = await page.evaluate("window.__cls")
        print(f"Cumulative Layout Shift (CLS): {cls_score:.4f}")
        assert cls_score < 0.02, f"CLS score {cls_score} exceeds 0.02 budget"

        # Check console errors
        print(f"Console errors: {console_errors}")
        assert len(console_errors) == 0, f"Found console errors: {console_errors}"

        # Capture desktop homepage screenshot
        await page.screenshot(path="docs/screenshots/home_desktop.png", full_page=True)
        print("PASS: Desktop full page screenshot saved to docs/screenshots/home_desktop.png")

        # Capture mobile viewport
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.goto("http://127.0.0.1:8000/home")
        await page.wait_for_timeout(600)
        await page.screenshot(path="docs/screenshots/home_mobile.png", full_page=True)
        print("PASS: Mobile full page screenshot saved to docs/screenshots/home_mobile.png")

        # Capture dashboard screenshot
        # Log in first
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.goto("http://127.0.0.1:8000/login")
        await page.fill("#login-email", "tester_smoke@axionfront.com")
        await page.fill("#login-password", "Password123!")
        await page.click("button[type='submit']")
        await page.wait_for_timeout(1500)
        await page.screenshot(path="docs/screenshots/dashboard_desktop.png", full_page=True)
        print("PASS: Dashboard screenshot saved to docs/screenshots/dashboard_desktop.png")

        await browser.close()

    if server_process:
        server_process.terminate()

if __name__ == "__main__":
    asyncio.run(verify_homepage())
