const input = document.querySelector('#reader-query');
const collection = document.querySelector('#reader-collection');
const count = document.querySelector('#reader-count');
const results = [...document.querySelectorAll('#reader-results li')];
const variants = [
  [/krishna|krushna/g, 'krsna'],
  [/shiva/g, 'siva'],
  [/vishnu/g, 'visnu'],
  [/lalitha/g, 'lalita'],
  [/\bshri\b/g, 'sri'],
  [/soundarya/g, 'saundarya'],
  [/saundarya\s+lahari/g, 'saundaryalahari'],
  [/chalisa/g, 'calisa'],
];

function normalize(value) {
  const folded = value.normalize('NFD').replace(/\p{Mark}/gu, '')
    .toLowerCase().replace(/[^\p{Letter}\p{Number}]+/gu, ' ').trim();
  return variants.reduce((text, [pattern, replacement]) => text.replace(pattern, replacement), folded);
}
const entries = results.map(item => {
  const link = item.querySelector('a');
  const groups = item.dataset.collections.split('|');
  return [item, normalize(`${link.textContent} ${link.pathname} ${groups.join(' ')}`), groups];
});

function showMatches() {
  const words = normalize(input.value).split(' ').filter(Boolean);
  let visible = 0;
  for (const [item, title, groups] of entries) {
    item.hidden = !words.every(word => title.includes(word)) ||
      Boolean(collection.value && !groups.includes(collection.value));
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
function updateAddress() {
  const query = input.value.trim();
  if (query) address.searchParams.set('q', query);
  else address.searchParams.delete('q');
  if (collection.value) address.searchParams.set('collection', collection.value);
  else address.searchParams.delete('collection');
  history.replaceState(history.state, '', address);
}
const selected = address.searchParams.get('collection');
if ([...collection.options].some(option => option.value === selected)) collection.value = selected;
input.addEventListener('change', updateAddress);
collection.addEventListener('change', () => {
  showMatches();
  updateAddress();
});
showMatches();
