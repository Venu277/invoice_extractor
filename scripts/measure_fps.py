import asyncio
from playwright.async_api import async_playwright

async def measure_fps():
    async with async_playwright() as p:
        browser = await p.chromium.launch(args=[
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-features=CalculateNativeWinOcclusion"
        ])
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Connect CDP session for CPU throttling
        client = await context.new_cdp_session(page)
        await client.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        print("CDP: 4x CPU throttling enabled")

        await page.goto("http://127.0.0.1:8000/home")
        await page.wait_for_timeout(1000)

        # Measure requestAnimationFrame delta times over 2 seconds
        fps_data = await page.evaluate("""
            new Promise((resolve) => {
                let frames = 0;
                const start = performance.now();
                function count(now) {
                    frames++;
                    if (now - start >= 2000) {
                        const fps = (frames / ((now - start) / 1000));
                        resolve({ frames, fps });
                    } else {
                        requestAnimationFrame(count);
                    }
                }
                requestAnimationFrame(count);
            });
        """)

        print(f"FPS under 4x CPU throttle: {fps_data['fps']:.1f} fps ({fps_data['frames']} frames in 2s)")
        assert fps_data['fps'] >= 55.0, f"Expected ~60 fps, got {fps_data['fps']}"
        await browser.close()

if __name__ == '__main__':
    asyncio.run(measure_fps())
