import { cookies } from "next/headers";
import { COOKIE } from "@/lib/server/opsSecurity.mjs";
import { hasEnquiryOrigin } from "@/lib/server/enquiryOrigin.mjs";
import { json } from "@/lib/server/opsApi";
export async function POST(request) {
  if (!hasEnquiryOrigin(request)) return json({error:"INVALID_ORIGIN"},403);
  (await cookies()).set(COOKIE,"",{httpOnly:true,secure:process.env.NODE_ENV === "production",sameSite:"strict",path:"/",maxAge:0});
  return json({success:true});
}
