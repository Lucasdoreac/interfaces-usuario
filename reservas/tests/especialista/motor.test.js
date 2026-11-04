import test from "node:test";
import assert from "node:assert/strict";
import { recomendar, localizacao, REGRAS } from "../../src/especialista/motor.js";
import { SALAS_SINTETICAS } from "../../src/especialista/dadosSinteticos.js";

const ids = (lista) => lista.map((a) => a.salaId).sort();

test("recomenda só salas que atendem todas as regras aplicáveis, com justificativa", () => {
  const r = recomendar(SALAS_SINTETICAS, { participantes: 30, recursos: ["projetor"], campus: "Sede" });
  assert.deepEqual(ids(r.recomendadas), ["s1"]);
  assert.deepEqual(ids(r.rejeitadas), ["s2", "s3"]);
  assert.deepEqual(ids(r.indeterminadas), ["s4"]);
  const just = r.recomendadas[0].justificativas;
  assert.deepEqual(just.map((j) => j.regra), ["capacidade", "recursos", "campus"]);
  assert.ok(just.every((j) => j.fato.fonte === "sintetico"));
});

test("dado ausente vira indeterminada, nunca recomendada", () => {
  const r = recomendar(SALAS_SINTETICAS, { participantes: 10 });
  assert.ok(!ids(r.recomendadas).includes("s4"));
  assert.match(r.indeterminadas[0].justificativas[0].motivo, /não informada/);
});

test("sem critério aplicável nada é recomendado", () => {
  const r = recomendar(SALAS_SINTETICAS, {});
  assert.equal(r.semCriterio, true);
  assert.equal(r.recomendadas.length, 0);
});

test("regras sem validação humana são sinalizadas", () => {
  const r = recomendar(SALAS_SINTETICAS, { participantes: 10 });
  assert.deepEqual(r.regrasNaoValidadas, ["capacidade"]);
  assert.ok(REGRAS.every((x) => x.validadaPor === null));
});

test("regra validada não é listada como pendente", () => {
  const validada = REGRAS.map((x) => (x.id === "capacidade" ? { ...x, validadaPor: "prof" } : x));
  assert.deepEqual(recomendar(SALAS_SINTETICAS, { participantes: 10 }, validada).regrasNaoValidadas, []);
});

test("localização lista o confirmado e o ausente, sem trajeto", () => {
  const completa = localizacao(SALAS_SINTETICAS[0]);
  assert.deepEqual(completa.ausentes, []);
  const parcial = localizacao(SALAS_SINTETICAS[1]);
  assert.deepEqual(parcial.ausentes, ["andar"]);
  const minima = localizacao(SALAS_SINTETICAS[3]);
  assert.deepEqual(minima.ausentes, ["predio", "andar"]);
  assert.equal(minima.trajeto, null);
  assert.ok(!("predio" in minima.conhecidos));
});

test("recomendação não altera as salas recebidas", () => {
  const antes = JSON.stringify(SALAS_SINTETICAS);
  recomendar(SALAS_SINTETICAS, { participantes: 30, campus: "Sede" });
  assert.equal(JSON.stringify(SALAS_SINTETICAS), antes);
});
