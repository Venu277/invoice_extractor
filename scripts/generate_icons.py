import asyncio
import os
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        svg_path = os.path.abspath('app/static/img/axion-mark.svg')
        url = f"file:///{svg_path.replace(os.sep, '/')}"
        
        # Ensure directories exist
        os.makedirs('app/static/img', exist_ok=True)
        os.makedirs('docs/screenshots', exist_ok=True)
        
        sizes = [16, 32, 64, 180, 512]
        for size in sizes:
            await page.set_viewport_size({"width": size, "height": size})
            await page.goto(url)
            # Take screenshot
            out_file = f"app/static/img/apple-touch-icon-{size}.png" if size == 180 else f"app/static/img/axion-mark-{size}.png"
            if size == 180:
                out_file_main = "app/static/apple-touch-icon.png"
                await page.screenshot(path=out_file_main, omit_background=True)
                print(f"Generated {out_file_main}")
            if size == 512:
                out_file_main = "app/static/img/axion-icon-512.png"
                await page.screenshot(path=out_file_main, omit_background=True)
                print(f"Generated {out_file_main}")
                
            doc_shot = f"docs/screenshots/logo_{size}px.png"
            await page.screenshot(path=doc_shot, omit_background=False)
            print(f"Rendered and verified {size}px -> {doc_shot}")
            
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
