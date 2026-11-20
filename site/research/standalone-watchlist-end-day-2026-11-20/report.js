'use strict';

const table = document.querySelector('.price-table');
const body = table.tBodies[0];
const rows = Array.from(body.rows);
const market = document.getElementById('market');
const sort = document.getElementById('sort');
const count = document.getElementById('visible-rows');

function updateRows() {
  const [horizon, direction] = sort.value.split(':');
  const ordered = [...rows];
  if (horizon) {
    const sign = direction === 'asc' ? 1 : -1;
    ordered.sort((a, b) => {
      const first = a.querySelector('[data-horizon="' + horizon + '"]').dataset.return;
      const second = b.querySelector('[data-horizon="' + horizon + '"]').dataset.return;
      if (first === '' || second === '') return Number(first === '') - Number(second === '');
      return sign * (Number(first) - Number(second));
    });
  }
  for (const row of ordered) {
    row.hidden = market.value !== 'all' && market.value !== row.dataset.market;
    body.append(row);
  }
  count.textContent = ordered.filter(row => !row.hidden).length + ' shares shown';
}

market.addEventListener('change', updateRows);
sort.addEventListener('change', updateRows);
document.getElementById('show-inputs').addEventListener('click', event => {
  const showing = table.classList.toggle('show-inputs');
  event.currentTarget.textContent = showing ? 'Hide base closes' : 'Show base closes';
  event.currentTarget.setAttribute('aria-pressed', String(showing));
});
document.getElementById('copy-prompt').addEventListener('click', async () => {
  const prompt = document.getElementById('prompt-text');
  const status = document.getElementById('copy-status');
  try {
    await navigator.clipboard.writeText(prompt.textContent.trim());
    status.textContent = 'Prompt copied.';
  } catch {
    const range = document.createRange();
    range.selectNodeContents(prompt);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    status.textContent = 'Prompt selected. Press Ctrl+C or Command+C to copy.';
  }
});
document.querySelectorAll('[data-js-only]').forEach(element => element.hidden = false);
