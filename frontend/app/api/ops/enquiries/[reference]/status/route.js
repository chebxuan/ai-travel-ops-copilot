import { backendOps, failure, json, session, smallJson } from "@/lib/server/opsApi";
import { hasEnquiryOrigin } from "@/lib/server/enquiryOrigin.mjs";
export async function POST(request, context) {
  if (!hasEnquiryOrigin(request)) return json({error:"INVALID_ORIGIN"},403);
  try {
    await session();
    const {reference} = await context.params;
    if (!/^TC-[A-F0-9]{16}$/.test(reference)) return json({error:"ENQUIRY_NOT_FOUND"},404);
    let data;
    try { data = await smallJson(request); } catch { return json({error:"INVALID_REQUEST"},400); }
    if (!Number.isInteger(data.expected_version) || data.expected_version<1 || !["new","following_up","proposal_sent","closed"].includes(data.status) || Object.keys(data).some(key=>!["status","expected_version"].includes(key))) return json({error:"INVALID_REQUEST"},400);
    return await backendOps("POST",`/api/ops/enquiries/${reference}/status`,"",JSON.stringify(data));
  } catch (error) { return failure(error); }
}
