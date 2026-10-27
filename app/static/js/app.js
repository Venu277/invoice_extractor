/**
 * Axion Core Frontend JavaScript
 * Liquid glass pointer tracking, collapsible sidebar, tooltips & modals.
 * Lightweight vanilla script (<15 KB).
 */

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initPointerHighlight();
  initPasswordToggles();
  initModals();
});

/* -------------------------------------------------------------
   1. Collapsible Sidebar & Mobile Drawer
   ------------------------------------------------------------- */
function initSidebar() {
  const sidebar = document.getElementById('appSidebar');
  const toggleBtn = document.getElementById('sidebarToggle');
  const scrim = document.getElementById('sidebarScrim');
  const mobileMenuBtn = document.getElementById('mobileMenuBtn');

  if (!sidebar) return;

  // Remove initial inline layout-shift prevention class so dynamic toggling works
  document.documentElement.classList.remove('sidebar-init-collapsed');

  // Restore saved preference
  const savedState = localStorage.getItem('axion_sidebar');
  if (savedState === 'collapsed' && window.innerWidth >= 900) {
    sidebar.classList.add('collapsed');
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'false');
  } else {
    sidebar.classList.remove('collapsed');
    if (toggleBtn) toggleBtn.setAttribute('aria-expanded', 'true');
  }

  // Toggle desktop collapsed / expanded
  if (toggleBtn) {
    toggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();

      if (window.innerWidth < 900) {
        closeMobileDrawer();
        return;
      }

      const isCollapsed = sidebar.classList.toggle('collapsed');
      localStorage.setItem('axion_sidebar', isCollapsed ? 'collapsed' : 'expanded');
      toggleBtn.setAttribute('aria-expanded', (!isCollapsed).toString());
    });
  }

  // Mobile drawer controls
  if (mobileMenuBtn) {
    mobileMenuBtn.addEventListener('click', (e) => {
      e.preventDefault();
      sidebar.classList.add('mobile-open');
      if (scrim) scrim.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
  }

  function closeMobileDrawer() {
    sidebar.classList.remove('mobile-open');
    if (scrim) scrim.classList.remove('active');
    document.body.style.overflow = '';
  }

  if (scrim) {
    scrim.addEventListener('click', closeMobileDrawer);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('mobile-open')) {
      closeMobileDrawer();
    }
  });

  // Responsive resize watcher
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 900) {
      closeMobileDrawer();
    }
  });
}

/* -------------------------------------------------------------
   2. Specular Pointer Highlight on Glass Panels
   ------------------------------------------------------------- */
function initPointerHighlight() {
  // Check prefers-reduced-motion
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

  const cards = document.querySelectorAll('.glass-interactive');
  cards.forEach(card => {
    card.addEventListener('mousemove', (e) => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', `${x}px`);
      card.style.setProperty('--mouse-y', `${y}px`);
    });
  });
}

/* -------------------------------------------------------------
   3. Password Reveal Toggles
   ------------------------------------------------------------- */
function initPasswordToggles() {
  const toggleButtons = document.querySelectorAll('.password-toggle-btn');
  toggleButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const wrap = btn.closest('.password-wrap');
      if (!wrap) return;
      const input = wrap.querySelector('input');
      const iconEye = btn.querySelector('.icon-eye');
      const iconEyeOff = btn.querySelector('.icon-eye-off');

      if (!input) return;

      if (input.type === 'password') {
        input.type = 'text';
        if (iconEye) iconEye.style.display = 'none';
        if (iconEyeOff) iconEyeOff.style.display = 'inline-block';
      } else {
        input.type = 'password';
        if (iconEye) iconEye.style.display = 'inline-block';
        if (iconEyeOff) iconEyeOff.style.display = 'none';
      }
    });
  });
}

/* -------------------------------------------------------------
   4. Modal Backdrop and Escape Key Handler
   ------------------------------------------------------------- */
function initModals() {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      const openModals = document.querySelectorAll('.modal-backdrop');
      openModals.forEach(m => {
        if (m.style.display !== 'none') {
          m.style.display = 'none';
        }
      });
    }
  });
}
