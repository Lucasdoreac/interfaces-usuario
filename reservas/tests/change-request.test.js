import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import EventStatus from "../src/utils/EventStatus.js";
import { changeRequestMessage, statusLabel } from "../src/utils/eventStatusLabel.js";

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

test("My Events renders the reason as text and no longer carries its own label table", () => {
  const source = read("../src/pages/meus-eventos/MyEvents.jsx");
  assert.match(source, /changeRequestMessage\(item\)/);
  assert.match(source, /Corrigir e reenviar/);
  assert.doesNotMatch(source, /dangerouslySetInnerHTML/);
  assert.doesNotMatch(source, /EventStatus\.Draft\b/, "EventStatus.Draft does not exist; the enum key is DRAFT");
});
