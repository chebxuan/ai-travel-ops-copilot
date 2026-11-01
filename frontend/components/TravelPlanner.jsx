"use client";
import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { products, availableDurations } from "@/data/products";
import { destinations } from "@/data/destinations";
import { createProductPreview } from "@/lib/productPreview";
import TripForm from "./TripForm";
import ContactPage from "./ContactPage";
import ItineraryPreview from "./ItineraryPreview";
import styles from "./Planner.module.css";

function PlannerWorkspace({ initialJourney, initialDestination }) {
  const initialCity = initialDestination?.name || initialJourney?.city || "";
  const initialDays = availableDurations(initialCity);
  const [form, setForm] = useState({ city: initialCity, days: String(initialJourney?.days || (initialDays.includes(3) ? 3 : initialDays[0]) || ""), date: "", adults: "2", children: "0", seniors: "0", optionalItems: [], car: false, routeChoice: "", notes: "" });
  const [catalogue, setCatalogue] = useState({ city: "", products: [], error: "" });
  const [retry, setRetry] = useState(0);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [enquiryBusy, setEnquiryBusy] = useState(false);
  const [error, setError] = useState("");
  const dirty = !!result && JSON.stringify(result.request) !== JSON.stringify(form);
  const preferredJourney = initialJourney?.city === form.city && initialJourney?.days === Number(form.days) ? initialJourney : null;
  const currentProduct = preferredJourney || products.find((product) => product.city === form.city && product.days === Number(form.days));
  const currentPublicProduct = catalogue.city === form.city ? catalogue.products.find((product) => product.product_id === currentProduct?.id) : null;
  const optionsLoading = !!form.city && catalogue.city !== form.city;
  const optionsError = catalogue.city === form.city ? catalogue.error : "";

  useEffect(() => {
    if (!form.city) return;
    const city = form.city;
    const controller = new AbortController();
    fetch(`/api/products?city=${encodeURIComponent(city)}`, { signal: controller.signal, cache: "no-store" })
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Service choices could not be loaded.");
        if (!controller.signal.aborted) setCatalogue({ city, products: data.products, error: "" });
      })
      .catch((error) => { if (!controller.signal.aborted) setCatalogue({ city, products: [], error: error.message || "Service choices could not be loaded." }); });
    return () => controller.abort();
  }, [form.city, retry]);

  function updateForm(nextForm) {
    if (nextForm.city !== form.city) {
      const durations = availableDurations(nextForm.city);
      nextForm = { ...nextForm, days: durations.includes(Number(nextForm.days)) ? nextForm.days : String(durations[0] || "") };
    }
    if (nextForm.city !== form.city || nextForm.days !== form.days) {
      nextForm = { ...nextForm, optionalItems: [], routeChoice: "" };
    } else if (nextForm.routeChoice !== form.routeChoice) {
      const route = currentPublicProduct?.quote_route_options.find((option) => option.choice === nextForm.routeChoice);
      nextForm = { ...nextForm, optionalItems: nextForm.optionalItems.filter((item) => !route?.excluded_optional_items.includes(item)) };
    }
    setForm(nextForm);
  }

  async function generate(event) {
    event.preventDefault();
    if (status === "loading") return;
    setStatus("loading");
    setError("");
    try {
      const preview = await createProductPreview(form, preferredJourney?.id, currentPublicProduct);
      setResult(preview);
      setStatus(preview ? "success" : "empty");
    } catch (error) {
      setStatus("error");
      setError(error.message || "Please try again or adjust your preferences.");
    }
  }
  return <div className={styles.workspace}><TripForm form={form} onChange={updateForm} onSubmit={generate} busy={status === "loading" || enquiryBusy} preparing={status === "loading"} preferredJourney={preferredJourney} currentProduct={currentProduct} publicProduct={currentPublicProduct} optionsLoading={optionsLoading} optionsError={optionsError} onRetry={() => setRetry((value) => value + 1)} selectedDestination={initialDestination?.name === form.city ? initialDestination : null} /><ItineraryPreview result={result} status={status} dirty={dirty} error={error} onEnquiryBusyChange={setEnquiryBusy} /></div>;
}

export default function TravelPlanner() {
  const searchParams = useSearchParams();
  const initialDestination = destinations.find((destination) => destination.slug === searchParams.get("destination"));
  const initialJourney = initialDestination ? null : products.find((journey) => journey.id === searchParams.get("journey"));
  if (!initialDestination && !initialJourney) return <ContactPage />;
  return <><div className={styles.pageHeading}><div><p className="eyebrow">DESIGNED AROUND YOU</p><h1>Discover your journey through China.</h1><p>The places, stories and experiences that could shape your days.</p></div></div><PlannerWorkspace key={initialDestination?.slug || initialJourney?.id || "custom"} initialJourney={initialJourney} initialDestination={initialDestination} /></>;
}
