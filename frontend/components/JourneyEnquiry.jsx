"use client";
import { useEffect, useRef, useState } from "react";
import Button from "./Button";
import { createEnquiryRequestId } from "@/lib/enquiryRequestId.mjs";
import Icon from "./Icon";
import styles from "./Planner.module.css";

export default function JourneyEnquiry({ result, visible, dirty, onBusyChange }) {
  const [open, setOpen] = useState(false);
  const [contact, setContact] = useState({ name: "", email: "", message: "", website: "" });
  const [submission, setSubmission] = useState({ status: "idle", error: "", reference: "" });
  const attempt = useRef(null);
  const inFlight = useRef(false);
  const nameInput = useRef(null);
  const previousPreview = useRef(null);

  useEffect(() => {
    if (open && submission.status === "idle") nameInput.current?.focus();
  }, [open, submission.status]);
  useEffect(() => {
    if (result?.enquiry?.previewToken !== previousPreview.current) {
      previousPreview.current = result?.enquiry?.previewToken;
      setSubmission({ status: "idle", error: "", reference: "" });
    }
  }, [result]);

  if (!result || !visible) return null;
  const busy = submission.status === "sending";
  const ready = !!result.enquiry?.previewToken && !dirty;
  function change(event) {
    setContact((value) => ({ ...value, [event.target.name]: event.target.value }));
  }
  async function submit(event) {
    event.preventDefault();
    if (!ready || inFlight.current) return;
    const payload = { name: contact.name.trim(), email: contact.email.trim(), message: contact.message.trim(), website: contact.website,
      preview_token: result.enquiry.previewToken, quote_token: result.enquiry.quoteToken || null,
      route_choices: result.route ? [{ day: result.route.day, choice: result.route.choice }] : [] };
    const fingerprint = JSON.stringify(payload);
    inFlight.current = true;
    onBusyChange(true);
    setSubmission({ status: "sending", error: "", reference: "" });
    try {
      if (attempt.current?.fingerprint !== fingerprint) attempt.current = { fingerprint, id: createEnquiryRequestId() };
      const response = await fetch("/api/trips/enquiries", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...payload, request_id: attempt.current.id }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "We could not save your enquiry. Please try again.");
      if (data.status !== "received" || !data.reference) throw new Error("We could not confirm your enquiry. Please try again.");
      setSubmission({ status: "received", error: "", reference: data.reference });
    } catch (error) {
      const message = ["TypeError", "SyntaxError"].includes(error.name) ? "We could not confirm your enquiry. Your details are still here; please try again." : error.message;
      setSubmission({ status: "error", error: message || "We could not save your enquiry. Your details are still here; please try again.", reference: "" });
    } finally {
      inFlight.current = false;
      onBusyChange(false);
    }
  }
  return <section className={styles.enquiryCard} aria-labelledby="enquiry-heading">
    <p className="eyebrow">YOUR JOURNEY, PERSONALLY PLANNED</p>
    <h3 id="enquiry-heading">Let’s make this journey yours.</h3>
    {submission.status === "received" ? <div className={styles.enquirySuccess} role="status"><Icon name="check" size={24} /><div><h4>We’ve received your enquiry.</h4><p>Your reference: <strong>{submission.reference}</strong></p><p>Our team can now review your journey and contact you at {contact.email.trim()}.</p><small>This is an enquiry, not a confirmed booking.</small></div></div> : <>
      <p>Share your journey with our team. We’ll help refine the details and confirm your arrangements.</p>
      {dirty && <p className={styles.enquiryHint} role="status">Your choices have changed. Preview your journey again before sending your enquiry.</p>}
      {!ready && !dirty && <p className={styles.enquiryHint} role="status">Preview your journey again to prepare your enquiry.</p>}
      {!open ? <Button disabled={!ready} className={styles.enquiryButton} onClick={() => setOpen(true)} aria-expanded={false} aria-controls="journey-enquiry-form">Talk to a Travel Expert <Icon /></Button> : <form id="journey-enquiry-form" onSubmit={submit} aria-busy={busy}>
        <div className={styles.enquirySummary}><strong>Your journey is already attached</strong><p>{result.product.menu.city_name} · {result.product.days} days · {Number(result.request.adults) + Number(result.request.children) + Number(result.request.seniors)} travellers{result.request.date ? ` · ${result.request.date}` : " · Dates to be confirmed"}</p>{result.route && <p>{result.route.label}</p>}<p>Accommodation is not included in this price. If you would like help arranging your stay, please contact our team.</p><small>Your selected experiences, services, notes and estimate will be included.</small></div>
        <fieldset className={styles.formFields} disabled={busy || !ready}>
          <div className={styles.enquiryFields}><label className={styles.field} htmlFor="enquiry-name"><span>Name</span><input ref={nameInput} id="enquiry-name" name="name" autoComplete="name" value={contact.name} onChange={change} required maxLength={120} /></label><label className={styles.field} htmlFor="enquiry-email"><span>Email</span><input id="enquiry-email" name="email" type="email" autoComplete="email" value={contact.email} onChange={change} required maxLength={254} /></label><label className={styles.field} htmlFor="enquiry-message"><span>Message <small>Optional</small></span><textarea id="enquiry-message" name="message" value={contact.message} onChange={change} rows={3} maxLength={2000} placeholder="Anything you’d like our team to know?" /></label></div>
          <div className={styles.enquiryTrap} aria-hidden="true"><label>Website<input name="website" value={contact.website} onChange={change} tabIndex={-1} autoComplete="off" /></label></div>
          <p className={styles.enquiryPrivacy}>We’ll use these details to reply about your journey. No account is needed.</p>
          {submission.error && <p className={styles.enquiryError} role="alert">{submission.error}</p>}
          <Button type="submit" className={styles.enquiryButton} disabled={!ready || busy}>{busy ? <><span className={styles.spinner} />Sending your enquiry</> : <>Send My Journey Enquiry <Icon /></>}</Button>
        </fieldset>
      </form>}
    </>}
  </section>;
}
