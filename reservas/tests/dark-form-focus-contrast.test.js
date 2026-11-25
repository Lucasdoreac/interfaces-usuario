import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
const css = readFileSync(new URL("../src/index.scss", import.meta.url), "utf8");
const app = readFileSync(new URL("../src/App.scss", import.meta.url), "utf8");
const lum = hex => [1,3,5].map(i => parseInt(hex.slice(i,i+2),16)/255).map(v => v <= 0.04045 ? v/12.92 : ((v+0.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[0.2126,0.7152,0.0722][i],0);
const ratio = (a,b) => { const x=lum(a), y=lum(b); return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };

test("dark errors and notices meet text contrast on the dark card", () => {
  assert.match(app, /body\.dark\s*\{[^}]*background-color:\s*#1d1d1d/);
  for (const name of ["form-error", "form-notice"]) {
    const color = css.match(new RegExp(`body\\.dark \\.${name}\\s*\\{\\s*color:\\s*(#[0-9a-f]{6})`, "i"))?.[1];
    assert.ok(color, name);
    assert.ok(ratio(color,"#1d1d1d") >= 4.5, `${name}: ${ratio(color,"#1d1d1d")}`);
  }
});

test("dark focus ring meets non-text contrast and header exceptions remain white", () => {
  const ring = css.match(/body\.dark :focus-visible\s*\{\s*outline-color:\s*(#[0-9a-f]{6})/i)?.[1];
  assert.ok(ring);
  assert.ok(ratio(ring,"#1d1d1d") >= 3, `focus: ${ratio(ring,"#1d1d1d")}`);
  assert.match(css, /body\.dark \.card-header :focus-visible,[\s\S]*?body\.dark span\.gradient :focus-visible\s*\{\s*outline-color:\s*#fff/i);
  assert.ok(ratio("#ffffff", "#0a2d7a") >= 3);
});
