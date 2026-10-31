/**
 * Axion Motion System
 * Apple-style and Qarin Framer-inspired lightweight motion engine.
 * Budget: < 12 KB unminified.
 */
(() => {
  // 1. Immediately mark JavaScript availability before first paint
  document.documentElement.classList.add('js');

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Indian number grouping formatter
  function formatIndianNumber(num, decimals = 0) {
    if (isNaN(num)) return '0';
    const parts = Number(num).toFixed(decimals).split('.');
    let intPart = parts[0];
    const decPart = parts.length > 1 ? '.' + parts[1] : '';
    const isNegative = intPart.startsWith('-');
    if (isNegative) intPart = intPart.slice(1);

    if (intPart.length > 3) {
      const lastThree = intPart.substring(intPart.length - 3);
      const remaining = intPart.substring(0, intPart.length - 3);
      intPart = remaining.replace(/\B(?=(\d{2})+(?!\d))/g, ',') + ',' + lastThree;
    }
    return (isNegative ? '-' : '') + intPart + decPart;
  }

  // 2. Prepare Words Reveal (accessible: sr-only full sentence + aria-hidden visual words)
  function initWordsReveal(el) {
    if (el.dataset.wordsInit) return;
    el.dataset.wordsInit = 'true';
    if (el.querySelector('.word-mask')) return; // Pre-rendered in HTML (zero CLS)

    const text = el.textContent.trim();
    if (!text) return;

    const words = text.split(/\s+/);
    const fragment = document.createDocumentFragment();

    const srSpan = document.createElement('span');
    srSpan.className = 'sr-only';
    srSpan.textContent = text;
    fragment.appendChild(srSpan);

    const visualSpan = document.createElement('span');
    visualSpan.setAttribute('aria-hidden', 'true');

    words.forEach((w, i) => {
      const mask = document.createElement('span');
      mask.className = 'word-mask';
      const inner = document.createElement('span');
      inner.className = 'word-inner';
      inner.style.setProperty('--d', `${i * 35}ms`);
      inner.textContent = w;
      mask.appendChild(inner);
      visualSpan.appendChild(mask);
      if (i < words.length - 1) {
        visualSpan.appendChild(document.createTextNode(' '));
      }
    });
    fragment.appendChild(visualSpan);

    el.innerHTML = '';
    el.appendChild(fragment);
  }

  // 3. Prepare Stagger delays on children
  function initStaggers(parent) {
    const step = parseInt(parent.dataset.stagger, 10) || 80;
    const children = Array.from(parent.children);
    children.forEach((child, i) => {
      child.style.setProperty('--d', `${i * step}ms`);
    });
  }

  // 4. Count-up Animation
  function runCountUp(el) {
    if (el.dataset.countDone) return;
    el.dataset.countDone = 'true';

    const target = parseFloat(el.dataset.count);
    if (isNaN(target)) return;

    const prefix = el.dataset.prefix || '';
    const suffix = el.dataset.suffix || '';
    const decimals = parseInt(el.dataset.decimals, 10) || 0;

    if (prefersReduced) {
      el.textContent = `${prefix}${formatIndianNumber(target, decimals)}${suffix}`;
      return;
    }

    const duration = 1400;
    let startTime = null;

    function tick(timestamp) {
      if (!startTime) startTime = timestamp;
      const elapsed = timestamp - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      const current = target * ease;
      el.textContent = `${prefix}${formatIndianNumber(current, decimals)}${suffix}`;

      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = `${prefix}${formatIndianNumber(target, decimals)}${suffix}`;
      }
    }
    requestAnimationFrame(tick);
  }

  // 5. Typewriter Animation (Accessible, zero layout shift)
  function initTypewriter(el) {
    if (el.dataset.twInit) return;
    el.dataset.twInit = 'true';

    const fullText = (el.dataset.typewriterText || el.textContent).trim();
    if (!fullText) return;

    let chars = Array.from(el.querySelectorAll('.typewriter-char'));
    let caret = el.querySelector('.typewriter-caret');

    // If not already pre-rendered, construct visual elements
    if (chars.length === 0) {
      const fragment = document.createDocumentFragment();
      const sr = document.createElement('span');
      sr.className = 'sr-only';
      sr.textContent = fullText;
      fragment.appendChild(sr);

      const visual = document.createElement('span');
      visual.setAttribute('aria-hidden', 'true');

      for (let i = 0; i < fullText.length; i++) {
        const charSpan = document.createElement('span');
        charSpan.className = 'typewriter-char';
        charSpan.textContent = fullText[i];
        visual.appendChild(charSpan);
        chars.push(charSpan);
      }

      caret = document.createElement('span');
      caret.className = 'typewriter-caret';
      visual.appendChild(caret);
      fragment.appendChild(visual);

      el.innerHTML = '';
      el.classList.add('typewriter-root');
      el.appendChild(fragment);
    }

    if (!caret) {
      caret = document.createElement('span');
      caret.className = 'typewriter-caret';
      el.appendChild(caret);
    }

    let isCompleted = false;
    function completeImmediately() {
      if (isCompleted) return;
      isCompleted = true;
      chars.forEach(c => c.classList.add('is-typed'));
      setTimeout(() => caret && caret.classList.add('is-hidden'), 2000);
    }

    if (prefersReduced) {
      completeImmediately();
      caret && caret.classList.add('is-hidden');
      return;
    }

    el.addEventListener('click', completeImmediately, { once: true });
    window.addEventListener('keydown', completeImmediately, { once: true });

    const twObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting && !isCompleted) {
          twObserver.unobserve(el);
          startTyping();
        }
      });
    }, { threshold: 0.35 });

    twObserver.observe(el);

    function startTyping() {
      let currentIndex = 0;
      const targetDuration = 1000; // Complete entire typewriter animation in strictly max 1 second
      const startOverall = performance.now();

      function step(now) {
        if (isCompleted) return;
        const elapsed = now - startOverall;
        const targetCount = Math.min(chars.length, Math.floor((elapsed / targetDuration) * chars.length));

        while (currentIndex < targetCount) {
          chars[currentIndex].classList.add('is-typed');
          currentIndex++;
        }

        if (currentIndex >= chars.length || elapsed >= targetDuration) {
          completeImmediately();
          return;
        }
        requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
  }

  // 6. Specular tracking
  function initSpecular(card) {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      card.style.setProperty('--mouse-x', `${x.toFixed(1)}%`);
      card.style.setProperty('--mouse-y', `${y.toFixed(1)}%`);
    });
  }

  // 7. Header compaction on scroll
  function initHeader() {
    const header = document.querySelector('.topbar-floating');
    if (!header) return;

    requestAnimationFrame(() => header.classList.add('is-loaded'));

    let ticking = false;
    window.addEventListener('scroll', () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          if (window.scrollY > 24) {
            header.classList.add('is-compact');
          } else {
            header.classList.remove('is-compact');
          }
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  }

  // 8. Hero interactive 3D tilt
  function initHeroTilt() {
    if (prefersReduced) return;
    const heroVisual = document.querySelector('[data-hero-visual]');
    if (!heroVisual) return;

    heroVisual.addEventListener('mousemove', (e) => {
      const rect = heroVisual.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      const rotateX = (-y * 8).toFixed(2);
      const rotateY = (x * 8).toFixed(2);
      heroVisual.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-2px)`;
    });

    heroVisual.addEventListener('mouseleave', () => {
      heroVisual.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0)';
    });
  }

  // 9. Main IntersectionObserver for reveal elements
  function initMotionSystem() {
    initHeader();
    initHeroTilt();

    document.querySelectorAll('[data-specular]').forEach(initSpecular);
    document.querySelectorAll('[data-stagger]').forEach(initStaggers);
    document.querySelectorAll('[data-reveal="words"]').forEach(initWordsReveal);
    document.querySelectorAll('[data-typewriter]').forEach(initTypewriter);

    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const target = entry.target;
          target.classList.add('is-revealed');
          target.classList.add('is-in');

          if (target.hasAttribute('data-count')) {
            runCountUp(target);
          }

          target.querySelectorAll('[data-count]').forEach(runCountUp);
          revealObserver.unobserve(target);
        }
      });
    }, {
      threshold: 0.20,
      rootMargin: '0px 0px -8% 0px'
    });

    document.querySelectorAll('[data-reveal], [data-count]').forEach(el => {
      revealObserver.observe(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMotionSystem);
  } else {
    initMotionSystem();
  }
})();
