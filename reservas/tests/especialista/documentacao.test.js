import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ESTADOS, SECOES } from "../../src/especialista/documentacao.js";

const itens = SECOES.flatMap((s) => s.itens);

test("todo item da documentação tem texto, fonte e estado conhecido", () => {
  assert.ok(itens.length > 0);
  for (const i of itens) {
    assert.ok(i.texto && i.fonte, JSON.stringify(i));
    assert.ok(i.estado in ESTADOS, `estado desconhecido: ${i.estado}`);
  }
});

test("seções têm ids únicos e a documentação não expõe e-mails nem telefones", () => {
  const ids = SECOES.map((s) => s.id);
  assert.equal(new Set(ids).size, ids.length);
  const texto = JSON.stringify(SECOES);
  assert.doesNotMatch(texto, /[\w.+-]+@[\w-]+\.[\w.]+/);
  assert.doesNotMatch(texto, /\(?\d{2}\)?\s?9?\d{4}-?\d{4}/);
});

test("lacunas ficam como pendentes, nunca como registradas", () => {
  for (const i of itens.filter((x) => x.fonte === "Lacuna")) assert.equal(i.estado, "pendente");
});

test("a rota /sistema-especialista está declarada e tem meta", () => {
  assert.match(readFileSync(new URL("../../app/routes.js", import.meta.url), "utf8"), /route\("sistema-especialista", "routes\/sistema-especialista\.jsx"\)/);
  assert.match(readFileSync(new URL("../../app/routes/sistema-especialista.jsx", import.meta.url), "utf8"), /pageMeta\("Sistema especialista"\)/);
});

import { CASOS_DE_USO, COMPONENTES, CLASSES, SEQUENCIA, TECNOLOGIAS } from "../../src/especialista/diagramas.js";

test("toda ligação dos diagramas aponta para elementos que existem", () => {
  for (const d of [CASOS_DE_USO, COMPONENTES, CLASSES]) {
    const ids = new Set(d.elementos.map((e) => e.id));
    assert.equal(ids.size, d.elementos.length, `${d.id}: ids repetidos`);
    for (const l of d.ligacoes) assert.ok(ids.has(l.de) && ids.has(l.para), `${d.id}: ${l.de}->${l.para}`);
    assert.ok(d.alternativa.length > 40, `${d.id} sem versão em texto`);
  }
  for (const m of SEQUENCIA.mensagens) {
    assert.ok(SEQUENCIA.participantes[m.de] && SEQUENCIA.participantes[m.para]);
  }
});

test("a lista de tecnologias cita onde conferir cada camada", () => {
  for (const t of TECNOLOGIAS) assert.ok(t.camada && t.itens && t.onde);
});
