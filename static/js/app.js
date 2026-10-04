(() => {
  const sidebar = document.getElementById('sidebar');
  const toggle = document.querySelector('.menu-toggle');
  if (sidebar && toggle) {
    toggle.addEventListener('click', () => {
      const open = sidebar.classList.toggle('open');
      toggle.setAttribute('aria-expanded', String(open));
    });
  }
  document.querySelectorAll('.app-alert').forEach((alert) => {
    window.setTimeout(() => alert.classList.add('fade'), 5000);
  });
})();

