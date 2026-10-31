import asyncio
import time
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={'width': 1440, 'height': 900})
        page = await context.new_page()

        print("Navigating to http://127.0.0.1:8000/home...")
        await page.goto("http://127.0.0.1:8000/home")

        # -------------------------------------------------------------
        # 1. VERIFY TYPEWRITER SPEED (<= 1.0s)
        # -------------------------------------------------------------
        print("\n--- Verifying Typewriter Animation Speed ---")
        # Scroll to about section to trigger intersection observer
        await page.locator('#about').scroll_into_view_if_needed()
        
        start_time = time.time()
        # Wait until all characters are typed or max 1.5s
        total_chars = await page.locator('.typewriter-char').count()
        print(f"Total typewriter characters: {total_chars}")

        # Poll typed characters
        typed_done = False
        duration = 0
        for _ in range(30): # 30 * 50ms = 1.5s
            await page.wait_for_timeout(50)
            typed_count = await page.locator('.typewriter-char.is-typed').count()
            if typed_count >= total_chars:
                duration = time.time() - start_time
                typed_done = True
                break

        print(f"Typewriter finished: {typed_done} in {duration:.2f}s ({typed_count}/{total_chars} chars)")
        assert typed_done, "Typewriter did not finish typing"
        assert duration <= 1.25, f"Typewriter took too long: {duration:.2f}s (must be <= 1.0s + observer margin)"

        # -------------------------------------------------------------
        # 2. VERIFY WORKFLOW TILES (Number + Title only, Click -> Expand Squircle -> Reverse)
        # -------------------------------------------------------------
        print("\n--- Verifying Workflow Tiles Interaction ---")
        await page.locator('#how-it-works').scroll_into_view_if_needed()
        await page.wait_for_timeout(400)

        # Screenshot initial tiles in grid
        await page.screenshot(path='docs/screenshots/workflow_tiles.png')
        print("Captured docs/screenshots/workflow_tiles.png")

        tiles = page.locator('.step-tile')
        tile_count = await tiles.count()
        print(f"Found {tile_count} workflow tiles")
        assert tile_count == 3, f"Expected 3 workflow tiles, found {tile_count}"

        # Check tile 1: Drop & Extract
        tile1 = tiles.nth(0)
        tile1_text = await tile1.inner_text()
        print(f"Tile 1 visible text:\n{tile1_text.strip()}")
        assert "Drop & Extract" in tile1_text
        assert "Upload PDF invoices or scans" not in tile1_text, "Description should NOT be visible on initial tile!"

        # Click tile 1 to open centered squircle modal
        print("\nClicking Tile 1 to expand...")
        await tile1.click()
        await page.wait_for_timeout(500)

        # Check modal overlay is active
        overlay = page.locator('#workflowOverlay')
        overlay_class = await overlay.get_attribute('class')
        assert 'is-visible' in overlay_class, f"Overlay should be visible, got: {overlay_class}"

        modal_title = await page.locator('#workflowModalTitle').inner_text()
        modal_desc = await page.locator('#workflowModalDesc').inner_text()
        print(f"Modal opened! Title: '{modal_title}'")
        print(f"Modal Description: '{modal_desc}'")
        assert modal_title == "Drop & Extract"
        assert "Upload PDF invoices or scans" in modal_desc

        # Screenshot open modal with blurred background
        await page.screenshot(path='docs/screenshots/workflow_modal_open.png')
        print("Captured docs/screenshots/workflow_modal_open.png")

        # Click outside the card (e.g. top-left corner of overlay) to trigger reverse compression
        print("\nClicking outside the modal card to trigger reverse animation...")
        await overlay.click(position={'x': 50, 'y': 50})
        await page.wait_for_timeout(500)

        # Check overlay is closed
        is_overlay_visible = await overlay.is_visible()
        print(f"Overlay visible after close: {is_overlay_visible}")
        assert not is_overlay_visible, "Overlay should be hidden after clicking outside"

        # Check tile 1 opacity is restored
        tile1_opacity = await tile1.evaluate('(el) => window.getComputedStyle(el).opacity')
        print(f"Tile 1 opacity restored to: {tile1_opacity}")
        assert float(tile1_opacity) >= 0.95

        # Screenshot after reverse compression
        await page.screenshot(path='docs/screenshots/workflow_modal_closed.png')
        print("Captured docs/screenshots/workflow_modal_closed.png")

        # Test Tile 2: Auto-Reconcile
        print("\nClicking Tile 2: Auto-Reconcile...")
        tile2 = tiles.nth(1)
        await tile2.click()
        await page.wait_for_timeout(500)

        modal_title2 = await page.locator('#workflowModalTitle').inner_text()
        modal_desc2 = await page.locator('#workflowModalDesc').inner_text()
        print(f"Modal 2 opened! Title: '{modal_title2}'")
        print(f"Modal 2 Description: '{modal_desc2}'")
        assert modal_title2 == "Auto-Reconcile"
        assert "Automated rules check GST numbers" in modal_desc2

        # Close via close button
        await page.locator('#workflowModalClose').click()
        await page.wait_for_timeout(450)
        assert not await overlay.is_visible(), "Overlay should close via close button"

        print("\nALL WORKFLOW & TYPEWRITER TESTS PASSED!")
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
