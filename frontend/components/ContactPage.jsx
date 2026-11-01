"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { createEnquiryRequestId } from "@/lib/enquiryRequestId.mjs";
import DestinationPhoto from "./DestinationPhoto";
import Button from "./Button";
import Icon from "./Icon";
import styles from "./Planner.module.css";
import contactStyles from "./Contact.module.css";

export default function ContactPage() {
  const [form, setForm] = useState({ name: "", email: "", destinations: "", travel_dates: "", duration: "", travellers: "2", interests: "", message: "", website: "" });
  const [submission, setSubmission] = useState({ status: "idle", error: "", reference: "" });
  const attempt = useRef(null);
  const inFlight = useRef(false);
  const busy = submission.status === "sending";
  function change(event) { setForm((value) => ({ ...value, [event.target.name]: event.target.value })); }
  async function submit(event) {
    event.preventDefault();
    if (inFlight.current) return;
    const fields = form;
    const payload = { ...Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.trim()])), travellers: Number(form.travellers) };
    const fingerprint = JSON.stringify(payload);
    inFlight.current = true;
    setSubmission({ status: "sending", error: "", reference: "" });
    try {
      if (attempt.current?.fingerprint !== fingerprint) attempt.current = { fingerprint, id: createEnquiryRequestId() };
      const response = await fetch("/api/trips/custom-enquiries", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, request_id: attempt.current.id }) });
      const data = await response.json();
      if (!response.ok || data.status !== "received" || !data.reference) throw new Error(data.error || "We could not confirm your enquiry. Please try again.");
      setSubmission({ status: "received", reference: data.reference, error: "" });
    } catch (error) {
      setSubmission({ status: "error", reference: "", error: ["TypeError", "SyntaxError"].includes(error.name) ? "We could not confirm your enquiry. Your details are still here; please try again." : error.message });
    } finally { inFlight.current = false; }
  }
  return <div className={contactStyles.layout}>
    <aside className={contactStyles.story}><p className="eyebrow">LET’S BEGIN A CONVERSATION</p><h1>Your China story<br /><em>starts with you.</em></h1><p>A place you’ve dreamed of. A craft you’re curious about. A little more time to simply wander. Tell us what draws you to China.</p><div className={contactStyles.photo}><DestinationPhoto slug="yunnan" /><span>Old lanes. New perspectives.</span></div><p>Still finding your direction? That’s a good place to start.</p><Link href="/#destinations" className={contactStyles.link}>Find a little inspiration <Icon size={18} /></Link></aside>
    <section className={`${styles.formCard} ${contactStyles.card}`} aria-labelledby="contact-title">
      {submission.status === "received" ? <div className={contactStyles.success} role="status"><Icon name="check" size={36} /><p className="eyebrow">YOUR ENQUIRY IS SAVED</p><h2>Thank you for sharing your ideas.</h2><p>Your reference: <strong>{submission.reference}</strong></p><p>Our team can use your preferences to shape a personal proposal. This is an enquiry, not a confirmed booking.</p><Button href="/#destinations">Keep exploring <Icon /></Button></div> : <form onSubmit={submit} aria-busy={busy} id="custom-enquiry-form"><h2 id="contact-title">Tell us about your journey.</h2><p className={contactStyles.intro}>Only your name and email are required. Share as much or as little as you know.</p><fieldset className={styles.formFields} disabled={busy}>
      <div className={styles.fieldRow}>{[{ name: "name", label: "Your Name", type: "text", max: 120 }, { name: "email", label: "Email", type: "email", max: 254 }].map((field) => <label key={field.name} className={styles.field} htmlFor={`contact-${field.name}`}><span>{field.label} <small>Required</small></span><input id={`contact-${field.name}`} name={field.name} type={field.type} value={form[field.name]} onChange={change} autoComplete={field.name} required maxLength={field.max} /></label>)}</div>
      <label className={styles.field} htmlFor="contact-destinations"><span>Where would you like to go? <small>Optional</small></span><input id="contact-destinations" name="destinations" value={form.destinations} onChange={change} maxLength={300} placeholder="A city, several places, or ‘help me decide’" /></label>
      <div className={styles.fieldRow}><label className={styles.field} htmlFor="contact-dates"><span>When are you thinking of travelling?</span><input id="contact-dates" name="travel_dates" value={form.travel_dates} onChange={change} maxLength={120} placeholder="Exact dates, a month, or not sure yet" /></label><label className={styles.field} htmlFor="contact-duration"><span>How long would you like to stay?</span><input id="contact-duration" name="duration" value={form.duration} onChange={change} maxLength={120} placeholder="For example, around a week" /></label></div>
      <label className={styles.field} htmlFor="contact-travellers"><span>Number of Travellers</span><input id="contact-travellers" name="travellers" type="number" min={1} max={60} required value={form.travellers} onChange={change} /></label>
      <p className={styles.catalogHint}>Accommodation is not included in this price. If you would like help arranging your stay, please contact our team.</p>
      <label className={styles.field} htmlFor="contact-interests"><span>What would make this journey special?</span><textarea id="contact-interests" name="interests" value={form.interests} onChange={change} rows={3} maxLength={1000} placeholder="Tea culture, local food, history, nature, family time…" /></label>
      <label className={styles.field} htmlFor="contact-message"><span>Anything else we should know?</span><textarea id="contact-message" name="message" value={form.message} onChange={change} rows={3} maxLength={2000} placeholder="Your travel pace, accessibility needs, or any questions." /></label>
      <div className={styles.enquiryTrap} aria-hidden="true"><label>Website<input name="website" value={form.website} onChange={change} tabIndex={-1} autoComplete="off" /></label></div><p className={styles.enquiryPrivacy}>We’ll use your details to reply about your journey. No account is needed.</p>{submission.error && <p className={styles.enquiryError} role="alert">{submission.error}</p>}<Button type="submit" disabled={busy} className={styles.generateButton}>{busy ? "Sending your enquiry…" : "Send My Enquiry"}<Icon /></Button>
    </fieldset></form>}
    </section>
  </div>;
}
