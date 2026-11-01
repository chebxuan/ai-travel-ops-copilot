export async function createProductPreview(form, preferredId, productOptions) {
  const payload = { city: form.city, days: Number(form.days), ...(preferredId ? { product_id: preferredId } : {}),
    adults: Number(form.adults), children: Number(form.children), seniors: Number(form.seniors),
    travel_date: form.date || null, need_guide: true, need_private_car: form.car,
    selected_optional_items: [...form.optionalItems], notes: form.notes };
  const response = await fetch("/api/trips/preview", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
  if (response.status === 404) return null;
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "Your journey could not be prepared.");
  const route = (productOptions || data.product)?.quote_route_options.find((option) => option.choice === form.routeChoice);
  const guide = productOptions?.quote_guide_options.find((option) => option.code.endsWith("-GUIDE-01"));
  let quote;
  let quoteToken = null;
  if (!productOptions || !guide || (productOptions.quote_route_options.length > 0 && !route)) {
    quote = { status: "pending_confirmation", amount: null, notice: !productOptions ? "Service choices could not be loaded. Please retry before requesting an estimate." : !route && productOptions.quote_route_options.length > 0 ? "Choose your preferred route to see its estimate." : "We will confirm standard guide availability and your estimate with you." };
  } else {
    try {
      const quoted = await fetch("/api/trips/quote", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, product_id: data.product.product_id, is_peak: false,
          guide_code: guide.code, route_choices: route ? [{ day: route.day, choice: route.choice }] : [] }),
      });
      const body = await quoted.json();
      if (!quoted.ok) throw new Error(body.error || "We could not prepare your estimate.");
      quote = body.sales_quote;
      quoteToken = body.quote_token;
    } catch (error) {
      quote = { status: "unavailable", amount: null, notice: error.message || "Your estimate is temporarily unavailable. Preview again to retry." };
    }
  }
  return { product: data.product, experiences: data.selected_experiences, quote,
    enquiry: { previewToken: data.preview_token, quoteToken },
    guideLabel: guide?.label,
    route, request: { ...form, optionalItems: [...form.optionalItems] } };
}
