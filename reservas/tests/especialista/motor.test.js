import test from "node:test";
import assert from "node:assert/strict";
import { fato, localizacao, STATUS } from "../../src/especialista/motor.js";

const f = (valor) => ({ valor, fonte: "catálogo /rooms", confirmadoEm: null });

test("fato ausente, vazio ou nulo é tratado como ausente", () => {
  const sala = { id: "1", rotulo: "A", fatos: { campus: f("c1"), predio: f(""), andar: f(null) } };
  assert.equal(fato(sala, "campus").valor, "c1");
  assert.equal(fato(sala, "predio"), null);
  assert.equal(fato(sala, "andar"), null);
  assert.equal(fato(sala, "capacidade"), null);
  assert.equal(fato(undefined, "campus"), null);
});

test("localização lista o conhecido e o ausente, sem trajeto", () => {
  const completa = localizacao({ id: "1", rotulo: "A", fatos: { campus: f("c1"), predio: f("Bloco"), andar: f(2) } });
  assert.deepEqual(completa.ausentes, []);
  const so = localizacao({ id: "2", rotulo: "B", fatos: { campus: f("c1") } });
  assert.deepEqual(so.ausentes, ["predio", "andar"]);
  assert.equal(so.trajeto, null);
  assert.ok(!("predio" in so.conhecidos));
  assert.deepEqual(localizacao({ id: "3", rotulo: "C", fatos: {} }).ausentes, ["campus", "predio", "andar"]);
});

test("os três status existem", () => {
  assert.deepEqual(Object.values(STATUS).sort(), ["atende", "indeterminada", "nao_atende"]);
});
