import assert from "node:assert/strict";
import { webcrypto } from "node:crypto";
import { createEnquiryRequestId } from "../lib/enquiryRequestId.mjs";

const uuidV4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
// HTTP browsers expose secure randomness without exposing randomUUID.
const httpCrypto = { getRandomValues: webcrypto.getRandomValues.bind(webcrypto) };
const ids = Array.from({ length: 1000 }, () => createEnquiryRequestId(httpCrypto));
assert(ids.every((id) => uuidV4.test(id)));
assert.equal(new Set(ids).size, ids.length);
assert(uuidV4.test(createEnquiryRequestId(webcrypto)));
assert.throws(() => createEnquiryRequestId({}), /could not prepare/);
assert.throws(() => createEnquiryRequestId({ getRandomValues() { throw new Error("Randomness unavailable"); } }), /Randomness unavailable/);
console.log("PASS: HTTP fallback UUIDs, secure-context UUIDs and unavailable randomness.");
