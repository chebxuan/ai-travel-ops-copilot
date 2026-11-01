// Verify the production shell never freezes a build-time authentication result.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const directory = new URL("../.next/", import.meta.url);
const manifest = JSON.parse(await readFile(new URL("prerender-manifest.json", directory), "utf8"));
const html = await readFile(new URL("server/app/ops.html", directory), "utf8");
assert.equal(manifest.routes["/ops"]?.renderingMode, "PARTIALLY_STATIC", "Operations must evaluate runtime credentials on each request");
assert.equal(manifest.routes["/ops"]?.compute, "resuming", "Operations must retain request-time rendering");
assert.ok(html.includes("正在检查登录状态"), "The static shell should only show the neutral session placeholder");
assert.ok(!html.includes("运营入口尚未配置"), "Missing build-time credentials must not freeze the unavailable screen");
assert.ok(!html.includes('type="password"'), "The login result must be evaluated at request time");
console.log("Operations production shell: request-time auth preserved, build-time errors not frozen: PASS");
