'use strict';
(() => {
  const rows = document.querySelector('#contents-rows');
  if (!rows) return;
  const template = rows.firstElementChild.cloneNode(true);
  rows.addEventListener('click', e => {
    if (e.target.matches('[data-remove-row]')) e.target.closest('.contents-row').remove();
  });
  document.querySelector('#add-row').addEventListener('click', () => {
    const row = template.cloneNode(true);
    row.querySelectorAll('input').forEach(input => { input.value = ''; });
    rows.append(row); row.querySelector('input').focus();
  });
})();
