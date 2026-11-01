import { travelResponse } from "@/lib/server/travelApi";
export async function GET(request) {
  const city = new URL(request.url).searchParams.get("city");
  if (!city || city.length > 100) return Response.json({ error: "Choose a destination." }, { status: 400 });
  return travelResponse(`products?city=${encodeURIComponent(city)}`);
}
