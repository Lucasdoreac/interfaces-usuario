import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  DRAFT_CONFLICT_MESSAGE,
  DRAFT_ERROR_MESSAGE,
  draftSaveFailure,
  isDraftConflict,
} from "../src/utils/draftSaveFailure.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("a 409 from the API is the already-submitted conflict, anything else is a generic failure", () => {
  const conflict = { response: { status: 409, data: { error: "EventNotEditable" } } };
  assert.equal(isDraftConflict(conflict), true);
  assert.deepEqual(draftSaveFailure(conflict), { kind: "conflict", message: DRAFT_CONFLICT_MESSAGE });
  for (const other of [{ response: { status: 500 } }, { response: { status: 403 } }, new Error("Network Error"), null, undefined]) {
    assert.equal(isDraftConflict(other), false);
    assert.deepEqual(draftSaveFailure(other), { kind: "error", message: DRAFT_ERROR_MESSAGE });
  }
});

test("the messages tell the person what happened and where to go", () => {
  assert.match(DRAFT_CONFLICT_MESSAGE, /já foi enviado para aprovação em outra aba/);
  assert.match(DRAFT_CONFLICT_MESSAGE, /Meus Eventos/);
  assert.match(DRAFT_ERROR_MESSAGE, /Não foi possível salvar/);
});

test("saveDraft records why it failed and clears the notice on the next try or a new event", () => {
  const source = read("../src/context/FormContext.jsx");
  assert.match(source, /draftSaveFailure\(error\)/, "saveDraft must classify the error");
  assert.match(source, /setSaveFailure\(null\)/, "the notice must be cleared");
  assert.match(source, /saveFailure,/, "the context must expose saveFailure");
});

test("the steps show the notice as an alert with a way out", () => {
  const buttons = read("../src/components/TwoButtons/index.jsx");
  assert.match(buttons, /<DraftSaveAlert\s*\/>/, "the shared step buttons must render the notice");
  const alert = read("../src/components/DraftSaveAlert/index.jsx");
  assert.match(alert, /role="alert"/);
  assert.match(alert, /to="\/event\/mine"/, "link to Meus Eventos");
  assert.match(alert, /fillOutFormData\(""\)/, "button that starts a new event");
  assert.match(alert, /\/event\/type-selection/);
});
