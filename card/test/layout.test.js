import assert from 'node:assert/strict';
import test from 'node:test';

globalThis.window = { customCards: [] };
const definitions = new Map();
globalThis.customElements = { get: name => definitions.get(name), define: (name, ctor) => definitions.set(name, ctor) };
await import('../src/intex-pool-card.js');
const Card = definitions.get('intex-pool-card');

test('Sections allows long schedule cards to determine their own row height', () => {
  const card = new Card();
  assert.equal(card.getGridOptions().rows, undefined);
  assert.equal(card.getGridOptions().columns, 12);
});

test('Masonry size follows the rendered height of a long schedule card', () => {
  const card = new Card();
  Object.defineProperty(card, 'shadowRoot', {value: {querySelector: () => ({getBoundingClientRect: () => ({height: 386})})}});
  assert.equal(card.getCardSize(), 8);
});
