// The canonical site is server configuration, never a client-controlled forwarded header.
export function hasEnquiryOrigin(request) {
  const site = process.env.SITE_ORIGIN || process.env.SITE_ADDRESS;
  try {
    const expected = site
      ? new URL(site.includes("://") ? site : `https://${site}`).origin
      : new URL(request.url).origin;
    return request.headers.get("origin") === expected;
  } catch {
    return false;
  }
}
