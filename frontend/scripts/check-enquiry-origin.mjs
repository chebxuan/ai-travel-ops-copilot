import assert from "node:assert/strict";
import { hasEnquiryOrigin } from "../lib/server/enquiryOrigin.mjs";

const original = process.env.SITE_ADDRESS;
const originalOrigin = process.env.SITE_ORIGIN;
const request = (origin, headers = {}) => new Request("http://localhost:3000/api/trips/enquiries", {
  headers: { ...(origin === undefined ? {} : { origin }), ...headers },
});
try {
  delete process.env.SITE_ADDRESS;
  delete process.env.SITE_ORIGIN;
  assert.equal(hasEnquiryOrigin(request("http://localhost:3000")), true);
  assert.equal(hasEnquiryOrigin(request("https://elsewhere.example")), false);
  process.env.SITE_ADDRESS = "http://192.0.2.10";
  assert.equal(hasEnquiryOrigin(request("http://192.0.2.10")), true);
  assert.equal(hasEnquiryOrigin(request("http://localhost:3000")), false);
  process.env.SITE_ORIGIN = "http://192.0.2.10:8080";
  assert.equal(hasEnquiryOrigin(request("http://192.0.2.10:8080")), true);
  assert.equal(hasEnquiryOrigin(request("http://192.0.2.10")), false);
  delete process.env.SITE_ORIGIN;
  process.env.SITE_ADDRESS = "travel.example.com";
  assert.equal(hasEnquiryOrigin(request("https://travel.example.com")), true);
  assert.equal(hasEnquiryOrigin(request("http://travel.example.com")), false);
  assert.equal(hasEnquiryOrigin(request("https://elsewhere.example", {
    host: "elsewhere.example", "x-forwarded-host": "elsewhere.example", "x-forwarded-proto": "https",
  })), false);
  assert.equal(hasEnquiryOrigin(request(undefined)), false);
  assert.equal(hasEnquiryOrigin(request("null")), false);
  process.env.SITE_ADDRESS = "not a valid domain";
  assert.equal(hasEnquiryOrigin(request("http://localhost:3000")), false);
  console.log("Enquiry origin: development, IP, HTTPS, cross-site, spoofed headers and invalid configuration passed.");
} finally {
  if (original === undefined) delete process.env.SITE_ADDRESS;
  else process.env.SITE_ADDRESS = original;
  if (originalOrigin === undefined) delete process.env.SITE_ORIGIN;
  else process.env.SITE_ORIGIN = originalOrigin;
}
