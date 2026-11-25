import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../src/App.scss', import.meta.url), 'utf8');
const luminance = hex => {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map(v => v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126*r + 0.7152*g + 0.0722*b;
};
test('dark frames use a softened color with at least 3:1 contrast', () => {
  const color = css.match(/body\.dark\s*\{[^}]*--dark-border:\s*(#[\da-f]{6})/i)?.[1];
  assert.ok(color);
  assert.notEqual(color.toLowerCase(), '#ffffff');
  assert.ok((luminance(color) + 0.05) / (luminance('#1d1d1d') + 0.05) >= 3);
  for (const selector of ['body\\.dark \\.card', 'body\\.dark input\\[type="email"\\]', 'body\\.dark \\.btn:not\\(\\.btn-outline-primary\\)']) {
    assert.match(css.match(new RegExp(`${selector}\\s*\\{[^}]*\\}`))?.[0] ?? '', /border(?:-color)?:[^;]*var\(--dark-border\)/);
  }
});
