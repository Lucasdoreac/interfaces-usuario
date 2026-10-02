import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { EVENT_STEPS, stepOf } from "../src/utils/eventSteps.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("#18 each wizard route has its position, in order", () => {
  assert.deepEqual(EVENT_STEPS.map((s) => s.path), [
    "/event/type-selection", "/event/basic-info", "/event/details",
    "/event/logistics", "/event/schedule", "/event/confirm-data",
  ]);
  assert.deepEqual(stepOf("/event/details"), { current: 3, total: 6, label: "Detalhes", percent: 50 });
  assert.equal(stepOf("/event/type-selection").current, 1);
  assert.equal(stepOf("/event/confirm-data").percent, 100);
  assert.equal(stepOf("/event/logistics/").current, 4);
});

test("#18 no indicator outside the wizard", () => {
  for (const path of ["/", "/organizer", "/auth/callback", "/event/mine", "/event/confirmation", "/event"]) {
    assert.equal(stepOf(path), null, path);
  }
});

test("#18 every wizard route in the router is covered by the indicator", () => {
  const routes = read("../app/routes.js");
  for (const { path } of EVENT_STEPS) {
    assert.ok(routes.includes(`route("${path.replace("/event/", "")}"`), `${path} must exist in the router`);
  }
});

test("#18 the indicator is shown by the event layout and announces its state", () => {
  assert.match(read("../app/routes/event-layout.jsx"), /<StepIndicator \/>\s*<Outlet \/>/);
  const component = read("../src/components/StepIndicator/StepIndicator.jsx");
  assert.match(component, /role="progressbar"/);
  assert.match(component, /aria-valuenow=\{step\.current\}/);
});
