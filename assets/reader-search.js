const input = document.querySelector('#reader-query');
const count = document.querySelector('#reader-count');
const results = [...document.querySelectorAll('#reader-results li')];
const normalize = value => value.normalize('NFD').replace(/\p{Mark}/gu, '')
  .toLowerCase().replace(/krishna|krushna/g, 'krsna').replace(/[^\p{Letter}\p{Number}]+/gu, ' ').trim();
const entries = results.map(item => {
  const link = item.querySelector('a');
  return [item, normalize(`${link.textContent} ${link.pathname}`)];
});

function showMatches() {
  const words = normalize(input.value).split(' ').filter(Boolean);
  let visible = 0;
  for (const [item, title] of entries) {
    item.hidden = !words.every(word => title.includes(word));
    if (!item.hidden) visible++;
  }
  count.textContent = visible === 0
    ? 'No matching articles. Try a different spelling or a shorter search.'
    : visible === 1 ? '1 result' : `${visible} results`;
}

const address = new URL(location.href);
input.value = address.searchParams.get('q') ?? '';
document.querySelector('.reader-search-input').hidden = false;
input.addEventListener('input', showMatches);
input.addEventListener('change', () => {
  const query = input.value.trim();
  if (query) address.searchParams.set('q', query);
  else address.searchParams.delete('q');
  history.replaceState(history.state, '', address);
});
showMatches();
