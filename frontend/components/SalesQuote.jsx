import styles from "./Planner.module.css";

export default function SalesQuote({ quote, dirty }) {
  const estimated = quote?.status === "estimated" && !dirty;
  const money = estimated ? new Intl.NumberFormat("en", { style: "currency", currency: quote.currency, currencyDisplay: "code" }).format(quote.amount) : null;
  return <section className={styles.quoteCard} aria-labelledby="quote-heading" aria-live="polite">
    <p className="eyebrow">YOUR JOURNEY ESTIMATE</p>
    <h3 id="quote-heading">{dirty ? "Update your estimate" : estimated ? "Estimated Group Price" : quote?.status === "unavailable" ? "Estimate unavailable" : "Quote to be confirmed"}</h3>
    {estimated && <><p className={styles.quoteAmount}>{money}</p><p>For {quote.travellers} travellers · Standard season estimate</p><p>Seasonal adjustments and guide availability will be confirmed with you.</p></>}
    <p>Accommodation is not included in this price. If you would like help arranging your stay, please contact our team.</p>
    <p className={styles.quoteNotice}>{dirty ? "Your choices have changed. Preview again to refresh the route and price." : quote?.notice || "Confirm your preferences to receive an estimate."}</p>
    {estimated && <details className={styles.quoteScope}><summary>What your estimate includes</summary><div><section><h4>Included</h4><ul>{quote.included.map((item) => <li key={item}>{item}</li>)}</ul></section><section><h4>Not included</h4><ul>{quote.excluded.map((item) => <li key={item}>{item}</li>)}</ul></section></div></details>}
  </section>;
}
