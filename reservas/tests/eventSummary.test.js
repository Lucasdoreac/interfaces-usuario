import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { summarizeEventData } from "../src/utils/eventSummary.js";

const byLabel = (rows) => Object.fromEntries(rows.map((r) => [r.label, r.value]));

test("shows readable labels for the filled fields", () => {
  const rows = byLabel(summarizeEventData({
    tituloEvento: "Semana da Enfermagem",
    classificacao: "lecture",
    descricaoEvento: "Palestra aberta",
    courseName: "ENFERMAGEM (BACHARELADO)",
    numeroParticipantes: "40",
    espacos: "Auditório",
  }));

  assert.deepEqual(rows, {
    "Título": "Semana da Enfermagem",
    "Tipo de evento": "Palestra",
    "Descrição": "Palestra aberta",
    "Curso vinculado": "ENFERMAGEM (BACHARELADO)",
    "Número de participantes": "40",
    "Espaço necessário": "Auditório",
  });
});

test("hides empty fields, empty objects, internal ids and the logo (issue #36)", () => {
  const rows = summarizeEventData({
    tituloEvento: "Evento",
    trilhaDesc: "",
    projetoDesc: undefined,
    logo: "dwcorp.com.br:9000/labtech/email-icones/magic-link.png",
    eventId: "abc",
    roomId: "sala-1",
    alunosMonitores: [],
    telefone: null,
  });

  assert.deepEqual(rows.map((r) => r.label), ["Título"]);
});

test("never returns raw JSON or internal keys as a value", () => {
  const rows = summarizeEventData({ tituloEvento: "X", odsId: { a: 1 }, eventId: "abc" });

  for (const row of rows) assert.doesNotMatch(String(row.value), /[{}]/);
});

test("trilha and projeto combine yes/no with their description", () => {
  const rows = byLabel(summarizeEventData({
    trilha: "sim", trilhaDesc: "Empreendedorismo social", projeto: "nao", projetoDesc: "",
  }));

  assert.equal(rows["Trilha empreendedora"], "Sim — Empreendedorismo social");
  assert.equal(rows["Projeto de extensão"], "Não");
});

test("monitors accept text or objects and become one list", () => {
  const rows = byLabel(summarizeEventData({ alunosMonitores: ["31891942", { name: "Ana", id: "30008021" }] }));

  assert.equal(rows["Alunos monitores"], "31891942, Ana");
});

test("formats the reservation date in pt-BR", () => {
  const rows = byLabel(summarizeEventData({ reservationDate: "2026-10-05T13:30:00.000Z" }));

  assert.match(rows["Data da reserva"], /05\/10\/2026/);
});

test("an empty or missing form yields no rows instead of failing", () => {
  assert.deepEqual(summarizeEventData({}), []);
  assert.deepEqual(summarizeEventData(undefined), []);
  assert.deepEqual(summarizeEventData(null), []);
});

test("the confirm screen renders the summary, not a JSON dump", () => {
  const screen = readFileSync(new URL("../src/pages/event-confirm-data/EventConfirmData.jsx", import.meta.url), "utf8");

  assert.doesNotMatch(screen, /JSON\.stringify\(formData/);
  assert.match(screen, /summarizeEventData\(formData\)/);
});
