import { travelPost } from "@/lib/server/travelApi";
export async function POST(request) { return travelPost(request, "trips/quote"); }
