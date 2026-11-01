import { cookies } from "next/headers";
import { hasEnquiryOrigin } from "@/lib/server/enquiryOrigin.mjs";
import { COOKIE, SESSION_SECONDS, configuration, verifyPassword, issueSession, allowLogin } from "@/lib/server/opsSecurity.mjs";
import { json, failure, smallJson } from "@/lib/server/opsApi";
export async function POST(request) {
  if (!hasEnquiryOrigin(request)) return json({error:"INVALID_ORIGIN"}, 403);
  if (!allowLogin()) return json({error:"LOGIN_RATE_LIMIT"}, 429);
  let config;
  try { config = configuration(); } catch (error) { return failure(error); }
  try {
    const data = await smallJson(request);
    if (typeof data.username !== "string" || typeof data.password !== "string" || data.username.length > 80 || data.password.length > 256 || !data.password) return json({error:"INVALID_CREDENTIALS"},401);
    if (!await verifyPassword(data.username, data.password, config)) return json({error:"INVALID_CREDENTIALS"},401);
    (await cookies()).set(COOKIE, issueSession(config), { httpOnly:true, secure:process.env.NODE_ENV === "production", sameSite:"strict", path:"/", maxAge:SESSION_SECONDS });
    return json({success:true});
  } catch { return json({error:"INVALID_REQUEST"},400); }
}
