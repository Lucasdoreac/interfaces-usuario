// Evidence for the issues the Web PR closes or is expected to close.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { showCourseSearch } from "../src/utils/courseField.js";
import {
  descriptionDisabled,
  staleDescriptionReset,
  validateLogistics,
} from "../src/utils/eventLogistics.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

// Issue #35: auxiliary text of the Yes/No fields.
test("#35 'Sim' without text blocks the step; 'Não' needs no text", () => {
  assert.deepEqual(validateLogistics({ trilha: "nao", projeto: "nao" }), {});
  assert.deepEqual(validateLogistics({}), {});
  assert.deepEqual(Object.keys(validateLogistics({ trilha: "sim", trilhaDesc: "   " })), ["trilhaDesc"]);
  assert.deepEqual(Object.keys(validateLogistics({ projeto: "sim" })), ["projetoDesc"]);
  assert.deepEqual(
    Object.keys(validateLogistics({ trilha: "sim", projeto: "sim", trilhaDesc: "x", projetoDesc: "" })),
    ["projetoDesc"],
  );
  assert.deepEqual(validateLogistics({ trilha: "sim", trilhaDesc: "Trilha X", projeto: "sim", projetoDesc: "Y" }), {});
});

test("#35 the auxiliary text is read-only unless the selector is 'Sim'", () => {
  assert.equal(descriptionDisabled("nao"), true);
  assert.equal(descriptionDisabled(undefined), true);
  assert.equal(descriptionDisabled("sim"), false);
});

test("#35 going back to 'Não' clears the stale text", () => {
  assert.deepEqual(staleDescriptionReset("trilha", "nao"), { name: "trilhaDesc", value: "" });
  assert.deepEqual(staleDescriptionReset("projeto", "nao"), { name: "projetoDesc", value: "" });
  assert.equal(staleDescriptionReset("trilha", "sim"), null);
  assert.equal(staleDescriptionReset("espacos", "nao"), null);
});

test("#35 the step is wired to those rules", () => {
  const source = read("../src/pages/event-logistics/EventLogistics.jsx");
  assert.match(source, /validateLogistics\(formData\)[\s\S]*saveDraft\(\)/, "validation must run before the draft is saved");
  assert.match(source, /disabled=\{descriptionDisabled\(formData\.trilha/);
  assert.match(source, /disabled=\{descriptionDisabled\(formData\.projeto/);
  assert.match(source, /onChange=\{handleSelectChange\}/);
});

// Issues #37 and #25: "Curso Vinculado" keeps the saved course.
test("#37/#25 a draft with a course shows its label, even when it loads after the step mounted", () => {
  assert.equal(showCourseSearch({ courseId: 12, editing: false }), false);
  assert.equal(showCourseSearch({ courseId: undefined, editing: false }), true);
  assert.equal(showCourseSearch({ courseId: null, editing: false }), true);
  // the user pressing "Alterar curso"
  assert.equal(showCourseSearch({ courseId: 12, editing: true }), true);
});

test("#37/#25 the details step derives the field from the form data, not from a value read once on mount", () => {
  const source = read("../src/pages/event-details/EventDetails.jsx");
  assert.match(source, /showCourseSearch\(\{ courseId: formData\.courseId, editing: editingCourse \}\)/);
  assert.doesNotMatch(source, /useState\(!formData\.courseId\)/);
});

// Issue #24: no types request on the organizer's home screens.
test("#24 the home and login screens do not request the event types", () => {
  for (const file of ["../src/pages/Home/Home.jsx", "../src/pages/organizer/Organizer.jsx", "../src/PrivateRoute.jsx"]) {
    assert.doesNotMatch(read(file), /getTypes/, `${file} must not request the types`);
  }
  assert.match(read("../src/context/FormContext.jsx"), /getTypes/, "the types belong to the event form context");
  assert.match(read("../app/routes/event-layout.jsx"), /FormProvider/, "and only the event routes mount that context");
});
