// Imported only by server Route Handlers. Fixed paths never expose the cost API.
export async function travelResponse(path, payload, { enquiry = false } = {}) {
  const base = process.env.BACKEND_BASE_URL;
  const key = process.env.BACKEND_API_KEY;
  if (!base || !key) return Response.json({ error: "Journey services are temporarily unavailable." }, { status: 503 });
  try {
    const response = await fetch(`${base.replace(/\/$/, "")}/api/v3/${path}`, {
      method: payload === undefined ? "GET" : "POST",
      headers: { "Content-Type": "application/json", "X-API-Key": key },
      ...(payload === undefined ? {} : { body: JSON.stringify(payload) }),
      cache: "no-store", signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) {
      if (enquiry) {
        const problem = await response.json().catch(() => ({}));
        const code = problem.detail?.code;
        const status = [409, 422, 429, 503].includes(response.status) ? response.status : 502;
        const error = code === "PREVIEW_EXPIRED" ? "Your preview has expired. Preview your journey again, then send your enquiry." : code === "ENQUIRY_RETRY_CONFLICT" ? "Your enquiry details have changed. Please try again." : status === 422 ? "Please check your name, email and journey details. You may need to preview your journey again." : status === 429 ? "Please wait before sending another enquiry." : "We could not save your enquiry. Your details are still here; please try again.";
        return Response.json({ error }, { status, headers: { "Cache-Control": "no-store" } });
      }
      const status = [404, 422].includes(response.status) ? response.status : 502;
      return Response.json({ error: status === 404 ? "No standard journey matches this selection." : status === 422 ? "Please check your travellers, route and service choices." : "We could not prepare your journey. Please try again." }, { status });
    }
    return Response.json(await response.json(), { status: enquiry ? response.status : 200, headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ error: "We could not reach the journey service. Please try again." }, { status: 503 });
  }
}

export async function travelPost(request, path, { maxBytes = 16384, enquiry = false } = {}) {
  const reader = request.body?.getReader();
  if (!reader) return Response.json({ error: "Please provide your trip preferences." }, { status: 400 });
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > maxBytes) { await reader.cancel(); return Response.json({ error: "Your request is too long." }, { status: 413 }); }
      chunks.push(value);
    }
    const payload = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    return travelResponse(path, payload, { enquiry });
  } catch {
    return Response.json({ error: "Please check your trip preferences." }, { status: 400 });
  }
}
