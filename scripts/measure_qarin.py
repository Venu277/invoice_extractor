import json
import time
from playwright.sync_api import sync_playwright

def measure_site():
    results = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        
        for width, name in [(1440, "desktop"), (390, "mobile")]:
            print(f"Measuring {name} at {width}px...")
            page = browser.new_page(viewport={"width": width, "height": 900})
            page.goto("https://qarin.framer.website/", wait_until="networkidle")
            time.sleep(2)
            
            # Inspect animations and elements
            measurements = page.evaluate("""() => {
                const report = {};
                
                // 1. Check all document animations
                const anims = document.getAnimations().map(a => {
                    const effect = a.effect;
                    const timing = effect ? effect.getComputedTiming() : null;
                    return {
                        id: a.id,
                        playState: a.playState,
                        duration: timing ? timing.duration : null,
                        delay: timing ? timing.delay : null,
                        easing: timing ? timing.easing : null,
                        targetTag: effect && effect.target ? effect.target.tagName : null,
                        targetClass: effect && effect.target ? effect.target.className : null,
                        keyframes: effect && effect.getKeyframes ? effect.getKeyframes() : null
                    };
                });
                report.activeAnimations = anims.slice(0, 30);
                
                // 2. Buttons and text rolls
                const buttons = Array.from(document.querySelectorAll('a, button')).filter(el => {
                    return el.innerText && el.innerText.trim().length > 0;
                });
                
                report.buttons = buttons.slice(0, 10).map(b => {
                    const style = window.getComputedStyle(b);
                    // check child elements for text roll
                    const children = Array.from(b.children).map(c => ({
                        tag: c.tagName,
                        text: c.innerText,
                        style: {
                            transform: window.getComputedStyle(c).transform,
                            transition: window.getComputedStyle(c).transition
                        }
                    }));
                    return {
                        text: b.innerText.trim().split('\\n')[0],
                        className: b.className,
                        transition: style.transition,
                        transform: style.transform,
                        children: children
                    };
                });
                
                // 3. Header
                const nav = document.querySelector('header, nav, [data-framer-name*="Nav"], [data-framer-name*="Header"]');
                if (nav) {
                    report.header = {
                        tag: nav.tagName,
                        classes: nav.className,
                        computedStyle: {
                            position: window.getComputedStyle(nav).position,
                            transform: window.getComputedStyle(nav).transform,
                            opacity: window.getComputedStyle(nav).opacity,
                            transition: window.getComputedStyle(nav).transition
                        }
                    };
                }
                
                // 4. Logo ticker / marquee
                const marquee = document.querySelector('[data-framer-name*="Marquee"], [data-framer-name*="Ticker"], [data-framer-name*="Logo"]');
                if (marquee) {
                    report.marquee = {
                        className: marquee.className,
                        style: {
                            animation: window.getComputedStyle(marquee).animation,
                            transform: window.getComputedStyle(marquee).transform
                        }
                    };
                }
                
                return report;
            }""")
            
            # Now scroll down in 25% increments and observe scroll behavior
            scroll_data = []
            max_scroll = page.evaluate("() => document.body.scrollHeight - window.innerHeight")
            for step in range(5):
                pos = int(max_scroll * (step / 4.0))
                page.evaluate(f"window.scrollTo(0, {pos})")
                time.sleep(0.8)
                step_info = page.evaluate(f"""() => {{
                    return {{
                        scrollY: window.scrollY,
                        headerTransform: document.querySelector('header, nav') ? window.getComputedStyle(document.querySelector('header, nav')).transform : null,
                        headerOpacity: document.querySelector('header, nav') ? window.getComputedStyle(document.querySelector('header, nav')).opacity : null
                    }};
                }}""")
                scroll_data.append(step_info)
                
            results[name] = {
                "measurements": measurements,
                "scroll_data": scroll_data
            }
            page.close()
            
        browser.close()
        
    with open("scripts/qarin_measurements.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("Measurements saved to scripts/qarin_measurements.json")

if __name__ == "__main__":
    measure_site()
