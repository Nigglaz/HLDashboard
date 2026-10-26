(() => {
  const key = 'phoca-theme';
  const system = matchMedia('(prefers-color-scheme: dark)');
  let preference = null;
  try { preference = localStorage.getItem(key); } catch {}
  const valid = (value) => value === 'dark' || value === 'light';

  function apply() {
    const theme = valid(preference) ? preference : system.matches ? 'dark' : 'light';
    document.documentElement.dataset.theme = theme;
    for (const button of document.querySelectorAll('[data-theme-toggle]')) {
      button.setAttribute('aria-pressed', String(theme === 'dark'));
      button.title = theme === 'dark' ? 'Hellen Modus aktivieren' : 'Dunklen Modus aktivieren';
      button.innerHTML = `<i data-lucide="${theme === 'dark' ? 'sun' : 'moon'}" aria-hidden="true"></i><span class="theme-icon-fallback" aria-hidden="true"></span>`;
    }
    if (globalThis.lucide) globalThis.lucide.createIcons();
  }

  apply();
  document.addEventListener('DOMContentLoaded', () => {
    apply();
    for (const button of document.querySelectorAll('[data-theme-toggle]')) {
      button.addEventListener('click', () => {
        preference = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        try { localStorage.setItem(key, preference); } catch {}
        apply();
      });
    }
  });
  system.addEventListener('change', () => { if (!valid(preference)) apply(); });
  globalThis.addEventListener('storage', (event) => {
    if (event.key === key || event.key === null) {
      preference = event.newValue;
      apply();
    }
  });
})();