import "server-only";
import { cookies } from "next/headers";
import { COOKIE, configuration, verifySession, assertion } from "./opsSecurity.mjs";
export const privateHeaders = { "Cache-Control": "no-store, private", "Vary": "Cookie", "X-Robots-Tag": "noindex, nofollow", "Referrer-Policy": "no-referrer" };
export function json(data, status = 200) { return Response.json(data, {status, headers: privateHeaders}); }
export async function session() {
  const cookieStore = await cookies();
  const config = configuration();
  const actor = verifySession(cookieStore.get(COOKIE)?.value, config);
  if (!actor) throw new Error("OPS_UNAUTHORIZED");
  return { actor, config };
}
export async function backendOps(method, path, query = "", body = "") {
  const { actor, config } = await session();
  try {
    const base = process.env.BACKEND_BASE_URL;
    if (!base) throw new Error();
    const response = await fetch(`${base.replace(/\/$/, "")}${path}${query ? "?" + query : ""}`, {
      method, cache: "no-store", redirect: "error", signal: AbortSignal.timeout(10000),
      headers: {"Content-Type": "application/json", "X-Ops-Assertion": assertion(actor, method, path, query, body, config)},
      ...(body ? {body} : {}),
    });
    if (!response.ok) {
      const code = ({404:"ENQUIRY_NOT_FOUND",409:"STATUS_CONFLICT",422:"INVALID_REQUEST"})[response.status] || "OPS_UNAVAILABLE";
      return json({error: code}, [404,409,422].includes(response.status) ? response.status : 503);
    }
    return json(await response.json());
  } catch { return json({error:"OPS_UNAVAILABLE"}, 503); }
}
export function failure(error) { return json({error: error.message === "OPS_UNAUTHORIZED" ? "OPS_UNAUTHORIZED" : "OPS_UNAVAILABLE"}, error.message === "OPS_UNAUTHORIZED" ? 401 : 503); }
export async function smallJson(request, maximum = 4096) {
  if (request.headers.get("content-type")?.split(";")[0] !== "application/json") throw new Error("INVALID_REQUEST");
  const reader = request.body?.getReader();
  if (!reader) throw new Error("INVALID_REQUEST");
  const chunks = []; let size = 0;
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > maximum) { await reader.cancel(); throw new Error("INVALID_REQUEST"); }
    chunks.push(Buffer.from(value));
  }
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}
