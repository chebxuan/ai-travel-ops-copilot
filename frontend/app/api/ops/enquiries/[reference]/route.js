import { backendOps, failure, json } from "@/lib/server/opsApi";
export async function GET(request, context) {
  try {
    const {reference} = await context.params;
    if (!/^TC-[A-F0-9]{16}$/.test(reference)) return json({error:"ENQUIRY_NOT_FOUND"},404);
    return await backendOps("GET",`/api/ops/enquiries/${reference}`);
  } catch (error) { return failure(error); }
}
