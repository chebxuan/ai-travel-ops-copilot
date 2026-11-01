import { backendOps, failure, json } from "@/lib/server/opsApi";
export async function GET(request) {
  try {
    const query = new URL(request.url).searchParams;
    const page = query.get("page") || "1", status = query.get("status") || "";
    if (!/^\d{1,6}$/.test(page) || Number(page)<1 || Number(page)>100000 || (status && !["new","following_up","proposal_sent","confirmed","closed"].includes(status))) return json({error:"INVALID_REQUEST"},400);
    const params = new URLSearchParams({page,limit:"20"});
    if (status) params.set("status",status);
    return await backendOps("GET","/api/ops/enquiries",params.toString());
  } catch (error) { return failure(error); }
}
