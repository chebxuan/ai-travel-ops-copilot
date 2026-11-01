import { createHash, createHmac, pbkdf2, randomBytes, timingSafeEqual } from "node:crypto";
import { promisify } from "node:util";
const derive = promisify(pbkdf2);
export const COOKIE = "travel_ops_session";
export const SESSION_SECONDS = 4 * 60 * 60;
const same = (a, b) => {
  const x = Buffer.from(a), y = Buffer.from(b);
  return x.length === y.length && timingSafeEqual(x, y);
};
export function configuration() {
  const username = process.env.OPS_USERNAME || "";
  const hash = process.env.OPS_PASSWORD_HASH || "";
  const key = process.env.OPS_SESSION_KEY || "";
  const backendKey = process.env.OPS_BACKEND_KEY || "";
  if (!/^[A-Za-z0-9_.@-]{1,80}$/.test(username) ||
      !/^pbkdf2_sha256:600000:[a-f0-9]{32}:[a-f0-9]{64}$/.test(hash) ||
      key.length < 32 || backendKey.length < 32 || key === backendKey ||
      backendKey === process.env.BACKEND_API_KEY || key === process.env.BACKEND_API_KEY) {
    throw new Error("OPS_UNAVAILABLE");
  }
  // Production operator login must have a canonical HTTPS origin.
  if (process.env.NODE_ENV === "production" && !/^https:\/\//.test(process.env.SITE_ORIGIN || "")) throw new Error("OPS_UNAVAILABLE");
  return { username, hash, key, backendKey };
}
export async function verifyPassword(username, password, config) {
  const [, iterations, salt, expected] = config.hash.split(":");
  const actual = (await derive(password, Buffer.from(salt, "hex"), Number(iterations), 32, "sha256")).toString("hex");
  return same(actual, expected) && same(username, config.username);
}
const fingerprint = (config) => createHash("sha256").update(config.username + config.hash).digest("hex");
export function issueSession(config, now = Math.floor(Date.now() / 1000)) {
  const payload = Buffer.from(JSON.stringify({actor: config.username, exp: now + SESSION_SECONDS, credentials: fingerprint(config), nonce: randomBytes(16).toString("hex")})).toString("base64url");
  return payload + "." + createHmac("sha256", config.key).update(payload).digest("hex");
}
export function verifySession(token, config, now = Math.floor(Date.now() / 1000)) {
  try {
    if (!token || token.length > 2048) return null;
    const [payload, signature, extra] = token.split(".");
    if (extra || !signature || !same(signature, createHmac("sha256", config.key).update(payload).digest("hex"))) return null;
    const data = JSON.parse(Buffer.from(payload, "base64url").toString());
    return data.exp > now && data.exp <= now + SESSION_SECONDS && data.actor === config.username &&
      data.credentials === fingerprint(config) ? data.actor : null;
  } catch { return null; }
}
export function assertion(actor, method, path, query, body, config, now = Math.floor(Date.now() / 1000)) {
  const payload = Buffer.from(JSON.stringify({actor, method, path, query, body: createHash("sha256").update(body).digest("hex"), exp: now + 60})).toString("base64url");
  return payload + "." + createHmac("sha256", config.backendKey).update(payload).digest("hex");
}
// One operator / one frontend instance. A bounded global gate avoids trusting spoofed IP headers.
let windowStart = 0, attempts = 0;
export function allowLogin(now = Date.now()) {
  if (now - windowStart >= 60000) { windowStart = now; attempts = 0; }
  attempts += 1;
  return attempts <= 10;
}
