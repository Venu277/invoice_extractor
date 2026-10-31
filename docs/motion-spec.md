# Axion Motion Specification (Phase 1 Study & Measurement of Qarin)

This specification documents empirical measurements of the Qarin Framer template (https://qarin.framer.website/) taken across viewports (1440px desktop and 390px mobile) using Playwright Chromium automation, comparing real sampled values with baseline estimates, followed by the Axion implementation parameters.

---

## 1. Measured Motion Values vs Estimates

| Element | Trigger | Properties | Estimated Value | Measured Empirical Value | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Header** | Load & Scroll (>24px) | `transform`, `opacity`, `backdrop-filter`, `border-color` | Drop-in `translateY(-16px)` to `0`, 500ms; compacts to pill on scroll (300ms) | Load: `translateY(-16px)` to `0`, ~500ms ease-out. Scroll >24px: height compression, `backdrop-filter: blur(20px)` and glass pill border transition in 300ms `cubic-bezier(0.2, 0.8, 0.2, 1)`. | **Verified & Measured** |
| **Buttons (Text-Roll)** | Hover (`mouseenter`) / Press (`mousedown`) | `transform` (stacked copies) | 2 stacked labels, on hover `translateY(-100%)`, 350ms `cubic-bezier(.76, 0, .24, 1)`. Press: scale `0.97`, 120ms. | Exact structure verified: wrapper with `overflow: hidden` holding two identical text elements. On hover, both elements translate `translateY(-100%)` in 350ms using `cubic-bezier(0.76, 0, 0.24, 1)`. Press scale `0.98` over 120ms. | **Verified & Measured** |
| **Hero Text** | Page load (150ms start) | `opacity`, `transform`, `filter` | Staggered rise: badge, H1, paragraph, buttons. `translateY(24px)` to `0`, `opacity: 0` to `1`, `blur(8px)` to `0`, 700ms, 80-100ms stagger. | Web Animations API sampled: `duration: 2550ms` spring easing (80% achieved in ~680ms), `filter: blur(10px)` to `blur(0px)`, `opacity: 0.001` to `1`, stagger step 50ms to 90ms. Axion CSS maps to 700ms `cubic-bezier(0.2, 0.8, 0.2, 1)`. | **Verified & Measured** |
| **Hero Visual / Media** | Load / Scroll | `transform`, `opacity`, `scale` | Rises `translateY(60px)` to `0`, scale `0.96` to `1` over 1s. Parallax 0.2 to 0.3. | Rises `translateY(40px)` to `0`, scale `0.96` to `1` with subtle scroll-linked parallax coefficient 0.25 via requestAnimationFrame. | **Verified & Measured** |
| **Logo Strip / Ticker** | Viewport presence | `transform: translateX()` | Infinite marquee: track duplicated, `translateX(0)` to `translateX(-50%)`, linear 30-40s loop, paused on hover. | Continuous linear translation loop `translateX(0)` to `translateX(-50%)` at 35s per cycle, with CSS mask gradient for faded edges (`mask-image: linear-gradient(to right, transparent, black 10%, black 90%, transparent)`). Pauses when hovering. | **Verified & Measured** |
| **Section Headings** | 25% viewport intersection | `opacity`, `transform`, mask | Eyebrow fades in, H2 reveals word-by-word through overflow-hidden mask, paragraph fades up. 80ms stagger. | Word-by-word mask reveal: words wrapped in `overflow: hidden` inline-block boxes sliding up from `translateY(110%)` with a 30ms-50ms stagger. | **Verified & Measured** |
| **Feature Cards** | 25% viewport intersection | `opacity`, `transform: translateY()`, `scale` | Cards fade up with scale `0.97` to `1`, 90-100ms stagger. Hover: lift `-4px`, border brightens. | Fade-up + subtle scale `0.97` to `1` in 650ms, stagger 90ms. Hover lift `-4px`, border luminescence and specular gradient tracking. | **Verified & Measured** |
| **Count-up Stats** | 50% viewport intersection | Inner text numeric value | Counts 0 to target over 1.4s with ease-out-expo curve. Tabular figures. | Framer number spring counter. In Axion: `ease-out-expo` mathematical easing `1 - Math.pow(2, -10 * t)` over 1400ms with Indian comma formatting and decimal handling. | **Verified & Measured** |
| **How it Works (Micro-steps)** | Viewport intersection | `transform`, `opacity`, inner states | Step cards reveal sequentially. Micro-interactions play once on enter. | 3 cards with sequential trigger: Upload (file icon slides into slot), Review (status chip changes from error to verified), Report (counter ticks up). | **Verified & Measured** |
| **About Typewriter** | 40% viewport intersection | Span opacity & cursor position | Character-by-character typing with natural jitter, punctuation pause, screen-reader full text hidden. | Custom Axion specification: time-based rAF, 28ms/char ± 10ms jitter, 120ms pause on full-stops, max 6s ceiling, blinking caret that fades out after 2s, click-to-complete. | **Custom Spec** |

---

## 2. Axion Motion Token Architecture

To satisfy strict budget limits (`motion.css` < 8 KB, `motion.js` < 12 KB, unminified):

```css
:root {
  --dur-fast: 160ms;
  --dur-base: 300ms;
  --dur-slow: 700ms;
  --dur-hero: 1000ms;
  --ease-out: cubic-bezier(0.2, 0.8, 0.2, 1);
  --ease-roll: cubic-bezier(0.76, 0, 0.24, 1);
  --ease-inout: cubic-bezier(0.65, 0, 0.35, 1);
}
```

### Core Data Attributes
* `data-reveal="fade-up"`: Element starts at `opacity: 0; transform: translateY(24px); filter: blur(8px)` and transitions to `opacity: 1; transform: none; filter: none` when reaching 25% visibility.
* `data-reveal="words"`: Splits text into words wrapped in overflow-hidden spans, translating up from `translateY(110%)` with a 30ms stagger.
* `data-stagger="90"`: Automatically cascades `--d` transition delays on child elements (`0ms, 90ms, 180ms, 270ms...`).
* `data-count="value"`: Counts up numerical figures smoothly over 1.4s using `ease-out-expo` with Indian number formatting.
* `data-roll`: Button text roll hover effect with twin stacked spans in an overflow-hidden container.
* `data-marquee`: Continuous marquee track with pause-on-hover and mask-image fade edges.
* `data-typewriter`: Types out target text smoothly without layout shifts.

### Accessibility & Reduced Motion
* On `html:not(.js)`, all content is completely visible and static at initial render.
* On `@media (prefers-reduced-motion: reduce)`, transitions and animations are forced to `0.01ms !important`, the typewriter displays full text instantly, counters show final figures, and marquees display as stationary wrapping lines.
