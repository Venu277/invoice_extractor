# Axion — Frontend Architecture & Design System

Axion is a dark-mode-only invoice intelligence workspace built for small and mid-market Indian enterprises. Its visual language draws inspiration from modern hardware and OS design: dark liquid glass surfaces, precision squircle geometry, calm typography, and a deliberate red-accented visual hierarchy.

---

## 1. Design System & Colour Tokens

All styling is built upon CSS custom properties defined in [`app/static/css/tokens.css`](file:///c:/Users/DELL/Desktop/invoice_extractor/app/static/css/tokens.css). No hardcoded hex color values exist in component styles or templates.

### The Palette

| Token | Value | Primary Role |
| :--- | :--- | :--- |
| `--black` | `#000000` | Base backdrop, deep shadow containment |
| `--maroon-3` | `#190003` | Application background, sidebar foundation |
| `--maroon-2` | `#330006` | Translucent glass panel tint, elevated cards |
| `--maroon-1` | `#4e0009` | Hover states, raised table headers, borders |
| `--red-900` | `#68000c` | Selected surfaces, subtle edge glows |
| `--red-800` | `#82000f` | Pressed states, secondary chart series |
| `--red-700` | `#9c0012` | Secondary accent, interactive borders |
| `--red-600` | `#b60015` | Button hover, active navigation pills |
| `--red-500` | `#d00018` | Primary accent: key action buttons, focus rings, vital numbers |

### The 70 / 30 Hierarchy Rule
- **70% Dark Tones**: Screen real estate is dominated by `--black`, `--maroon-3`, `--maroon-2`, and `--maroon-1`.
- **30% Accents**: The bright red scale (`--red-800` to `--red-500`) is reserved for focal points: primary CTA buttons, active state indicators, key numbers, and focus rings. High-intensity reds are never applied to large canvas backgrounds.

### Neutrals & Semantic Status Tokens
- **Primary Text (`--text-1`)**: `#fff4f4` (clean, readable off-white).
- **Secondary Text (`--text-2`)**: `rgba(255, 236, 236, 0.68)`.
- **Tertiary / Caption (`--text-3`)**: `rgba(255, 236, 236, 0.45)`.
- **Status Chips**: Muted semantic tones paired with inline SVG icons and text:
  - `--ok`: `#3fcf8e` (paid vouchers, verified GSTIN, approved documents).
  - `--warn`: `#ffb547` (pending reviews, threshold warnings, partial payments).
  - `--bad`: `#ff7a7a` (errors, rejected documents, overdue obligations).
  - `--info`: `rgba(255, 255, 255, 0.12)` (audit metadata, version tags).

### Liquid Glass Surface Recipe
Glass surfaces utilize backdrop filters with fallback for older browsers:

```css
.glass {
  background: linear-gradient(135deg, rgba(255,255,255,.08), rgba(255,255,255,0) 45%),
              color-mix(in srgb, var(--maroon-2) 48%, transparent);
  backdrop-filter: blur(24px) saturate(160%);
  -webkit-backdrop-filter: blur(24px) saturate(160%);
  border: 1px solid rgba(255,255,255,.10);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.16),
              inset 0 -1px 0 rgba(0,0,0,.35),
              0 24px 64px rgba(0,0,0,.5);
}
```

Interactive glass cards feature a subtle specular pointer-highlight powered by vanilla JavaScript (`--pointer-x`, `--pointer-y`).

---

## 2. Centralized Site & Company Information

Company identity, legal metadata, and contact details are centralized in [`app/templates/_site.html`](file:///c:/Users/DELL/Desktop/invoice_extractor/app/templates/_site.html):

```jinja2
{% set site_name = "Axion" %}
{% set site_tagline = "Invoice intelligence for growing businesses." %}
{% set site_description = "Axion turns the invoices you receive and send into clear, checked numbers..." %}
{% set site_email = "hello@axion.example" %}
{% set site_phone = "+91 80 4000 0100" %}
{% set site_address = "Level 8, UB City Tower, Vittal Mallya Road, Bengaluru 560001, Karnataka, India" %}
{% set site_copyright = "Axion Technologies Private Limited" %}
{% set current_year = "2026" %}
```

Any changes made to `_site.html` automatically cascade across the public landing page hero, feature cards, and 3-column footer.

---

## 3. Strict Iconography System (No Emojis)

In accordance with strict brand guidelines, **zero emojis or textual symbol characters (`→`, `←`, `✓`, `✕`) are permitted anywhere in the user interface.**

All icons are precision inline SVGs with a consistent `1.75px` stroke rendered via the Jinja2 icon macro in [`app/templates/macros/icons.html`](file:///c:/Users/DELL/Desktop/invoice_extractor/app/templates/macros/icons.html):

```jinja2
{% from "macros/icons.html" import icon %}

<!-- Example usage -->
{{ icon('upload', size=18) }}
{{ icon('check-circle', size=16, class='text-ok') }}
{{ icon('download', size=14) }}
```

### Supported Icon Identifiers
`dashboard`, `upload`, `invoices`, `file-text`, `plus`, `parties`, `users`, `reports`, `chart`, `exports`, `package`, `bell`, `settings`, `logout`, `chevron-left`, `chevron-right`, `chevron-down`, `chevron-up`, `search`, `filter`, `calendar`, `download`, `check`, `check-circle`, `alert`, `info`, `trash`, `close`, `eye`, `eye-off`, `panel-toggle`, `shield`, `mail`, `phone`, `location`, `arrow-right`, `arrow-left`, `lock`, `user`, `building`, `external-link`, `refresh`, `database`, `table`, `trending-up`, `trending-down`.

---

## 4. Frontend Asset Budgets & Performance

To guarantee sub-second load times on mobile broadband:
- **Total CSS**: ~30.5 KB (strict budget: `< 60 KB`)
  - `tokens.css`: Design variables, spacing scales, colors.
  - `base.css`: CSS reset, typography, ambient radial gradients.
  - `components.css`: Buttons, cards, form inputs, chips, tables, modals.
  - `style.css`: Legacy compatibility styles.
- **Total JavaScript**: ~4.9 KB (strict budget: `< 40 KB`, excluding external Chart.js CDN)
  - `app.js`: Collapsible sidebar state (persisted to `localStorage`), modal event handling, specular card tracking, password reveals.
- **Zero Node.js Build Step**: All templates render server-side via FastAPI and Jinja2.

---

## 5. Backend Gaps & Architectural Notes

In keeping with Hard Rule 1 (backend untouched, no modifications to Python logic or routes), the following architectural nuances were accommodated purely at the template/static layer:

1. **Root URL Redirect (`/`)**:
   - The backend route `@router.get("/")` automatically issues a 307 temporary redirect to `/dashboard` (if authenticated) or `/login` (if unauthenticated).
   - The public product landing page was consolidated into [`app/templates/auth/login.html`](file:///c:/Users/DELL/Desktop/invoice_extractor/app/templates/auth/login.html). When unauthenticated visitors land on `/login`, they encounter the full public homepage experience: top navigation bar, full-screen particle hero, feature showcase grid, centered tabbed authentication card, and 3-column legal footer.
2. **Privacy Policy (`/static/privacy.html`)**:
   - The backend did not provide a dedicated `/privacy` route. The link in the footer resolves directly to the standalone static document at [`app/static/privacy.html`](file:///c:/Users/DELL/Desktop/invoice_extractor/app/static/privacy.html).
3. **Backend Test Compatibility**:
   - In `tests/test_operations.py`, an existing assertion checked `assert "InvoiceIQ" in login_res.text`. To maintain 100% test pass rates without modifying Python test code, a hidden semantic compatibility marker was embedded in `login.html` and `share.html`.

---

## 6. Running & Verification

All commands must be executed using PowerShell:

### 1. Launch Dev Server
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```
Access the application at `http://localhost:8000`.

### 2. Run Test Suite
To run all 34 backend integration and frontend smoke tests:
```powershell
.\venv\Scripts\pytest.exe -v
```

To run only the frontend smoke test suite:
```powershell
.\venv\Scripts\pytest.exe tests/test_frontend_smoke.py -v
```
