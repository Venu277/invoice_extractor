import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
SCREENSHOTS_DIR = Path("screenshots/light_mode")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

JS_CHECK_LIGHT_UI = """
() => {
  function parseRgba(str) {
    if (!str || str === 'transparent') return [0, 0, 0, 0];
    const srgbMatch = str.match(/color\(srgb\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)(?:\s*\/\s*([\d.]+))?\)/);
    if (srgbMatch) {
      const r = Math.round(parseFloat(srgbMatch[1]) * 255);
      const g = Math.round(parseFloat(srgbMatch[2]) * 255);
      const b = Math.round(parseFloat(srgbMatch[3]) * 255);
      const a = srgbMatch[4] !== undefined ? parseFloat(srgbMatch[4]) : 1;
      return [r, g, b, a];
    }
    const m = str.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)/);
    if (m) {
      return [parseInt(m[1]), parseInt(m[2]), parseInt(m[3]), m[4] !== undefined ? parseFloat(m[4]) : 1];
    }
    return [0, 0, 0, 0];
  }

  function composite(fg, bg) {
    const a = fg[3] + bg[3] * (1 - fg[3]);
    if (a === 0) return [0, 0, 0, 0];
    const r = Math.round((fg[0] * fg[3] + bg[0] * bg[3] * (1 - fg[3])) / a);
    const g = Math.round((fg[1] * fg[3] + bg[1] * bg[3] * (1 - fg[3])) / a);
    const b = Math.round((fg[2] * fg[3] + bg[2] * bg[3] * (1 - fg[3])) / a);
    return [r, g, b, a];
  }

  function getEffectiveBg(el) {
    let cur = el;
    let comp = [0, 0, 0, 0];
    while (cur && cur !== document.documentElement) {
      const style = window.getComputedStyle(cur);
      const bg = parseRgba(style.backgroundColor);
      if (bg[3] > 0) {
        comp = composite(comp, bg);
        if (comp[3] >= 0.99) break;
      }
      cur = cur.parentElement;
    }
    // Default page background is honeydew (#effdee -> [239, 253, 238, 1])
    return composite(comp, [239, 253, 238, 1]);
  }

  function relativeLuminance(rgb) {
    const srgb = rgb.slice(0, 3).map(v => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * srgb[0] + 0.7152 * srgb[1] + 0.0722 * srgb[2];
  }

  function contrastRatio(l1, l2) {
    const light = Math.max(l1, l2);
    const dark = Math.min(l1, l2);
    return (light + 0.05) / (dark + 0.05);
  }

  const failures = [];
  const elements = Array.from(document.querySelectorAll('*'));

  for (const el of elements) {
    // Only check visible elements
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) continue;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) <= 0.01) continue;

    // Check (a): Relative luminance of background for cards and major containers (confirming light theme)
    if (rect.width >= 40 && rect.height >= 40 && (el.classList.contains('card') || el.classList.contains('glass') || el.classList.contains('sidebar'))) {
      const effBg = getEffectiveBg(el);
      const lum = relativeLuminance(effBg);
      // Light surfaces should have luminance >= 0.40
      if (lum < 0.40) {
        failures.push({
          type: 'luminance_too_dark',
          tag: el.tagName.toLowerCase(),
          className: el.className,
          selector: el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''),
          value: lum.toFixed(3),
          bg: `rgba(${effBg.join(',')})`,
          text: (el.innerText || '').slice(0, 30)
        });
      }
    }

    // Check (b): Text contrast for elements with direct text
    const hasDirectText = Array.from(el.childNodes).some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim().length > 0);
    if (hasDirectText) {
      const textColor = parseRgba(style.color);
      if (textColor[3] > 0.05) {
        const effBg = getEffectiveBg(el);
        const textLum = relativeLuminance(textColor);
        const bgLum = relativeLuminance(effBg);
        const ratio = contrastRatio(textLum, bgLum);

        const fontSize = parseFloat(style.fontSize);
        const isBold = parseInt(style.fontWeight) >= 600 || style.fontWeight === 'bold';
        const isLarge = fontSize >= 24 || (fontSize >= 18.66 && isBold);
        const minRatio = isLarge ? 3.0 : 4.5;

        if (ratio < minRatio) {
          failures.push({
            type: 'contrast',
            tag: el.tagName.toLowerCase(),
            className: el.className,
            selector: el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className ? '.' + el.className.trim().split(/\\s+/).join('.') : ''),
            ratio: ratio.toFixed(2),
            minRatio: minRatio,
            fontSize: `${fontSize}px`,
            textColor: `rgba(${textColor.join(',')})`,
            bgColor: `rgba(${effBg.join(',')})`,
            text: el.textContent.trim().slice(0, 40)
          });
        }
      }
    }
  }

  return failures;
}
"""


def run_checks():
    print("=" * 65)
    print("Starting Axion Light UI (Green Palette) Audit across Viewports")
    print("=" * 65)

    total_failures = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for width, height in [(1440, 900), (390, 844)]:
            mode = "desktop" if width > 500 else "mobile"
            print(f"\n--- Testing Viewport: {width}x{height} ({mode}) ---")

            context = browser.new_context(viewport={"width": width, "height": height})
            page = context.new_page()

            # 1. Public Homepage (/home)
            page.goto(f"{BASE_URL}/home")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_home.png"))

            fails = page.evaluate(JS_CHECK_LIGHT_UI)
            if fails:
                print(f"[{mode}] /home: {len(fails)} failures")
                for f in fails[:5]:
                    print("  ", f)
                total_failures += len(fails)
            else:
                print(f"[{mode}] /home: OK")

            # 1b. Dedicated Login / Auth Page (/login)
            page.goto(f"{BASE_URL}/login")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_login.png"))

            fails = page.evaluate(JS_CHECK_LIGHT_UI)
            if fails:
                print(f"[{mode}] /login: {len(fails)} failures")
                for f in fails[:5]:
                    print("  ", f)
                total_failures += len(fails)
            else:
                print(f"[{mode}] /login: OK")

            # 2. Check standalone privacy policy
            page.goto(f"{BASE_URL}/static/privacy.html")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_privacy.png"))
            fails = page.evaluate(JS_CHECK_LIGHT_UI)
            if fails:
                print(f"[{mode}] /static/privacy.html: {len(fails)} failures")
                for f in fails[:5]:
                    print("  ", f)
                total_failures += len(fails)
            else:
                print(f"[{mode}] /static/privacy.html: OK")

            # 3. Authenticate as seeded owner
            page.goto(f"{BASE_URL}/login")
            page.fill("#login-email", "owner@demo.com")
            page.fill("#login-password", "DemoPassword123!")
            page.click("button[type='submit']")
            page.wait_for_load_state("networkidle")

            # 4. Test Sidebar Collapsing interaction (desktop & mobile)
            if mode == "desktop":
                assert page.locator("#sidebarToggle").count() == 1, "Expected single collapse button in sidebar header"
                page.click("#sidebarToggle")
                page.wait_for_timeout(350)
                page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_sidebar_collapsed.png"))
                sidebar_width = page.evaluate("() => document.getElementById('appSidebar').offsetWidth")
                assert sidebar_width == 76, f"Expected 76px collapsed rail width, got {sidebar_width}px"
                print(f"[{mode}] Sidebar collapse toggle: SUCCESS (collapsed to {sidebar_width}px)")

                page.click("#sidebarToggle")
                page.wait_for_timeout(350)
                sidebar_width = page.evaluate("() => document.getElementById('appSidebar').offsetWidth")
                assert sidebar_width == 264, f"Expected 264px expanded width, got {sidebar_width}px"
                print(f"[{mode}] Sidebar expand toggle: SUCCESS (expanded to {sidebar_width}px)")
            else:
                page.click("#mobileMenuBtn")
                page.wait_for_timeout(350)
                page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_sidebar_mobile_open.png"))
                is_open = page.evaluate("() => document.getElementById('appSidebar').classList.contains('mobile-open')")
                assert is_open, "Expected sidebar mobile drawer to open"
                print(f"[{mode}] Mobile drawer open: SUCCESS")

                page.evaluate("() => document.getElementById('sidebarScrim').click()")
                page.wait_for_timeout(350)
                is_open = page.evaluate("() => document.getElementById('appSidebar').classList.contains('mobile-open')")
                assert not is_open, "Expected sidebar mobile drawer to close on scrim click"
                print(f"[{mode}] Mobile drawer close: SUCCESS")

            # 5. Authenticated routes to test
            routes = [
                ("dashboard", "/dashboard"),
                ("upload", "/upload"),
                ("invoices", "/invoices"),
                ("invoice_review", "/invoices/1/review"),
                ("new_invoice", "/invoices/new"),
                ("parties", "/parties"),
                ("party_ledger", "/parties/1/ledger"),
                ("reports", "/reports"),
                ("exports", "/exports"),
                ("alerts", "/alerts"),
                ("settings", "/settings"),
            ]

            for name, route in routes:
                page.goto(f"{BASE_URL}{route}")
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(SCREENSHOTS_DIR / f"{mode}_{name}.png"))

                fails = page.evaluate(JS_CHECK_LIGHT_UI)
                if fails:
                    print(f"[{mode}] {route}: {len(fails)} failures")
                    for f in fails[:5]:
                        print("  ", f)
                    total_failures += len(fails)
                else:
                    print(f"[{mode}] {route}: OK")

            context.close()

        browser.close()

    print("\n" + "=" * 65)
    if total_failures == 0:
        print("AUDIT SUCCESS: 0 light UI or contrast failures across all viewports!")
    else:
        print(f"AUDIT COMPLETED WITH {total_failures} TOTAL FAILURES.")
    print("=" * 65)
    return total_failures


if __name__ == "__main__":
    code = run_checks()
    sys.exit(0 if code == 0 else 1)
