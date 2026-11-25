import assert from "node:assert/strict";
import test from "node:test";
import { isAllowedOrganizerEmail } from "../src/utils/emailPolicy.js";

test("accepts institutional and explicitly approved organizer addresses", () => {
  assert.equal(isAllowedOrganizerEmail("person@udf.edu.br"), true);
  assert.equal(
    isAllowedOrganizerEmail(" Reviewer@CS.UDF.EDU.BR ", "reviewer@cs.udf.edu.br"),
    true,
  );
  assert.equal(
    isAllowedOrganizerEmail(
      "danrley.pereira@cs.udf.edu.br",
      "danrley.pereira@cs.udf.edu.br",
    ),
    true,
  );
});

test("does not open the developer subdomain to other users", () => {
  assert.equal(isAllowedOrganizerEmail("person@cs.udf.edu.br"), false);
  assert.equal(
    isAllowedOrganizerEmail(
      "reviewer@cs.udf.edu.br.attacker.example",
      "reviewer@cs.udf.edu.br",
    ),
    false,
  );
  assert.equal(isAllowedOrganizerEmail("@udf.edu.br"), false);
});
