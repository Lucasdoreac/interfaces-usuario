import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { runSingleFlight } from "../src/utils/singleFlight.js";

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("a second click while the first request is pending does not send again", async () => {
  const flag = { current: false };
  let calls = 0;
  let release;
  const pending = new Promise((resolve) => { release = resolve; });
  const action = async () => { calls += 1; await pending; return "sent"; };

  const first = runSingleFlight(flag, action);
  const second = runSingleFlight(flag, action);
  assert.equal(await second, undefined, "the second click must be ignored");
  release();
  assert.equal(await first, "sent");
  assert.equal(calls, 1);
});

test("the guard opens again after success and after a failure", async () => {
  const flag = { current: false };
  const seen = [];
  await runSingleFlight(flag, async () => "ok", (busy) => seen.push(busy));
  await assert.rejects(runSingleFlight(flag, async () => { throw new Error("boom"); }, (busy) => seen.push(busy)), /boom/);
  assert.deepEqual(seen, [true, false, true, false]);
  assert.equal(flag.current, false);
  assert.equal(await runSingleFlight(flag, async () => "again"), "again");
});

test("the steps that wait on the network disable the button and show the indicator", () => {
  for (const [file, label] of [
    ["../src/pages/event-logistics/EventLogistics.jsx", /disabled=\{submitting\}/],
    ["../src/pages/event-confirm-data/EventConfirmData.jsx", /disabled=\{submitting\}/],
  ]) {
    const source = read(file);
    assert.match(source, /runSingleFlight\(\s*flight,/, `${file} does not guard the request`);
    assert.match(source, label, `${file} does not disable the button while sending`);
    assert.match(source, /\{submitting && <Loading \/>\}/, `${file} shows no indicator`);
  }
  assert.match(read("../src/components/TwoButtons/index.jsx"), /disabled=\{disabled\}/);
});
