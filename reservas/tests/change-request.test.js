import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import EventStatus from "../src/utils/EventStatus.js";
import { changeRequestMessage, eventCardView, statusLabel } from "../src/utils/eventStatusLabel.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("every status has a Portuguese label, drafts included", () => {
  for (const status of Object.values(EventStatus)) {
    assert.notEqual(statusLabel(status), status, `${status} is shown raw`);
  }
  assert.equal(statusLabel(EventStatus.DRAFT), "Rascunho");
  assert.equal(statusLabel(undefined), "Desconhecido");
});

test("the coordinator's reason is shown only while changes are requested", () => {
  const request = { message: "  Trocar a sala.  " };
  assert.equal(changeRequestMessage({ status: EventStatus.REQUESTED_CHANGE, changeRequest: request }), "Trocar a sala.");
  assert.equal(changeRequestMessage({ status: EventStatus.WAITING, changeRequest: request }), null);
  assert.equal(changeRequestMessage({ status: EventStatus.REQUESTED_CHANGE }), null);
  assert.equal(changeRequestMessage({ status: EventStatus.REQUESTED_CHANGE, changeRequest: { message: "   " } }), null);
  assert.equal(changeRequestMessage({ status: EventStatus.REQUESTED_CHANGE, changeRequest: { message: 42 } }), null);
});

test("the card view shows the notice, reason and fix link only for requested changes", () => {
  const requested = { _id: "e1", status: EventStatus.REQUESTED_CHANGE, changeRequest: { message: "Trocar a sala." } };
  const view = eventCardView(requested);
  assert.deepEqual(view.changeNotice, { heading: "A Coordenação pediu alterações.", message: "Trocar a sala." });
  assert.deepEqual(view.editLink, { label: "Corrigir e reenviar", to: "/event/type-selection?eventId=e1" });

  // an older request without a stored reason still shows the notice, without a reason
  assert.equal(eventCardView({ _id: "e2", status: EventStatus.REQUESTED_CHANGE }).changeNotice.message, null);
});

test("the card view offers plain editing for drafts and nothing for submitted events", () => {
  const draft = eventCardView({ _id: "d1", status: EventStatus.DRAFT, changeRequest: { message: "old" } });
  assert.equal(draft.changeNotice, null);
  assert.deepEqual(draft.editLink, { label: "Editar Evento", to: "/event/type-selection?eventId=d1" });

  for (const status of [EventStatus.WAITING, EventStatus.APPROVED_BY_COORDENACAO, EventStatus.REJECTED_BY_REITORIA, undefined]) {
    const view = eventCardView({ _id: "x", status, changeRequest: { message: "old" } });
    assert.equal(view.changeNotice, null, `${status} shows a notice`);
    assert.equal(view.editLink, null, `${status} offers editing`);
  }
});

// Source-wiring check only: it reads MyEvents.jsx as text and does not render it. The repo has
// no DOM test setup, so what the logged-in page shows needs the E2E or a manual check.
test("source wiring: My Events uses the card view helper and renders its text without raw HTML", () => {
  const source = read("../src/pages/meus-eventos/MyEvents.jsx");
  assert.match(source, /eventCardView\(item\)/);
  assert.match(source, /changeNotice\.message/);
  assert.match(source, /editLink\.to/);
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(source, /EventStatus\.Draft\b/, "EventStatus.Draft does not exist; the enum key is DRAFT");
});
