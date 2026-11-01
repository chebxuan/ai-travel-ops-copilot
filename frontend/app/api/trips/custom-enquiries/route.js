import { travelPost } from "@/lib/server/travelApi";
import { hasEnquiryOrigin } from "@/lib/server/enquiryOrigin.mjs";

export async function POST(request) {
  if (!hasEnquiryOrigin(request)) {
    return Response.json({ error: "Please send your enquiry from this website." }, { status: 403 });
  }
  if (!request.headers.get("content-type")?.startsWith("application/json")) {
    return Response.json({ error: "Please check your enquiry details." }, { status: 415 });
  }
  return travelPost(request, "trips/custom-enquiries", { maxBytes: 16384, enquiry: true });
}
