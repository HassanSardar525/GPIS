(() => {
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  let choice = 'system';
  try {
    const saved = localStorage.getItem('gpis.theme');
    if (saved === 'light' || saved === 'dark') choice = saved;
  } catch { /* Browser storage is optional. */ }
  function apply() {
    root.dataset.theme = choice === 'system' ? (system.matches ? 'dark' : 'light') : choice;
  }
  apply();
  system.addEventListener('change', apply);
  document.addEventListener('DOMContentLoaded', () => {
    const control = document.querySelector('#theme-choice');
    control.value = choice;
    control.addEventListener('change', () => {
      choice = control.value;
      apply();
      try { localStorage.setItem('gpis.theme', choice); } catch { /* Keep the choice for this visit. */ }
    });
  });
})();
