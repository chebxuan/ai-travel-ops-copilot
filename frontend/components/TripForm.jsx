import { productCities, availableDurations, cityName, optionalName } from "@/data/products";
import Button from "./Button";
import Icon from "./Icon";
import styles from "./Planner.module.css";

export default function TripForm({ form, onChange, onSubmit, busy, preparing, preferredJourney, selectedDestination, currentProduct, publicProduct, optionsLoading, optionsError, onRetry }) {
  const routes = publicProduct?.quote_route_options || [];
  const selectedRoute = routes.find((option) => option.choice === form.routeChoice);
  const optionalItems = (currentProduct?.optionalItems || []).filter((item) => !selectedRoute?.excluded_optional_items.includes(item));
  function changeField(event) {
    const { name, value, type, checked } = event.target;
    onChange({ ...form, [name]: type === "checkbox" ? checked : value });
  }
  function toggleOptional(item) {
    onChange({ ...form, optionalItems: form.optionalItems.includes(item) ? form.optionalItems.filter((selected) => selected !== item) : [...form.optionalItems, item] });
  }
  return <form className={styles.formCard} onSubmit={onSubmit}>
    <div className={styles.cardHeading}><span className={styles.stepNumber}>01</span><div><h2>Tell us how you like to travel</h2><p>Start with a few simple choices.</p></div></div>
    {selectedDestination && <div className={styles.selectedJourney}><Icon name="location" size={18} /><span>Your destination: {cityName(selectedDestination.name)}<small>Choose your dates, duration and experiences.</small></span></div>}
    {preferredJourney && <div className={styles.selectedJourney}><Icon name="check" size={18} /><span>Selected: {preferredJourney.englishTitle}<small>Adjust your destination and duration below.</small></span></div>}
    <fieldset className={styles.formFields} disabled={busy}>
      <section className={styles.formSection} aria-labelledby="destination-heading"><h3 id="destination-heading"><Icon name="location" size={19} />Your Journey</h3>
        {!selectedDestination && <label className={styles.field} htmlFor="trip-city"><span>Destination <small>Required</small></span><select id="trip-city" name="city" value={form.city} onChange={changeField} required><option value="">Choose a destination</option>{productCities.map((city) => <option key={city} value={city}>{cityName(city)}</option>)}</select></label>}
        <div className={styles.fieldRow}><label className={styles.field} htmlFor="trip-date"><span>Start Date <small>Optional</small></span><input id="trip-date" name="date" type="date" value={form.date} onChange={changeField} /></label><label className={styles.field} htmlFor="trip-days"><span>Duration</span><select id="trip-days" name="days" value={form.days} onChange={changeField} required disabled={!form.city}>{!form.city && <option value="">Choose a destination first</option>}{availableDurations(form.city).map((days) => <option key={days} value={days}>{days} days</option>)}</select></label></div>
      </section>
      {optionsLoading && <p className={styles.catalogHint} role="status">Loading route and service choices…</p>}
      {optionsError && <div className={styles.catalogHint} role="alert"><p>{optionsError}</p><button className="button button--secondary" type="button" onClick={onRetry}>Retry service choices</button></div>}
      {routes.length > 0 && <fieldset className={styles.interestFieldset}><legend>Choose Your Day {routes[0].day}</legend><p>Pick one direction. Your estimate includes only your selected route.</p><div className={styles.optionalChoices}>{routes.map((route) => <label key={route.choice}><input type="radio" name="routeChoice" value={route.choice} checked={form.routeChoice === route.choice} onChange={changeField} /><span>{route.label}</span></label>)}</div></fieldset>}
      <section className={styles.formSection} aria-labelledby="travelers-heading"><h3 id="travelers-heading"><Icon name="people" size={19} />Your Travellers</h3><div className={styles.peopleFields}>{[{ name: "adults", label: "Adults", min: 1 }, { name: "children", label: "Children", min: 0 }, { name: "seniors", label: "Seniors", min: 0 }].map((person) => <label className={styles.field} key={person.name} htmlFor={`trip-${person.name}`}><span>{person.label}</span><input id={`trip-${person.name}`} name={person.name} type="number" min={person.min} max="20" required value={form[person.name]} onChange={changeField} /></label>)}</div></section>
      <fieldset className={styles.interestFieldset}><legend><Icon name="leaf" size={19} />Optional Experiences</legend>{!currentProduct ? <p>Choose your destination and duration to see optional experiences.</p> : optionalItems.length === 0 ? <p>There are no additional optional experiences for this journey.</p> : <><p>Select experiences or dining you would like to add to your estimate.</p><div className={styles.optionalChoices}>{optionalItems.map((item) => <label key={item}><input type="checkbox" name="optionalItems" value={item} checked={form.optionalItems.includes(item)} onChange={() => toggleOptional(item)} /><span>{optionalName(item)}</span></label>)}</div></>}</fieldset>
      <section className={styles.services}><h3>Your Services</h3><p className={styles.catalogHint}>A standard English-speaking guide is included in your estimate.</p><label><input name="car" type="checkbox" checked={form.car} onChange={changeField} /><span>I would like a private vehicle</span></label></section>
      <p className={styles.catalogHint}>Accommodation is not included in this price. If you would like help arranging your stay, please contact our team.</p>
      <details className={styles.extraNotes}><summary>Anything else in mind?<Icon name="chevron" size={16} /></summary><label className={styles.field} htmlFor="trip-notes"><span>Share your ideas</span><textarea id="trip-notes" name="notes" value={form.notes} onChange={changeField} rows={3} maxLength={2000} placeholder="For example: a slower pace, or more family-friendly experiences." /></label><p>Your ideas will be saved with your preview for later discussion.</p></details>
      <Button type="submit" className={styles.generateButton} disabled={busy}>{preparing ? <><span className={styles.spinner} />Preparing your journey</> : <>Preview My Journey <Icon /></>}</Button>
      <p className={styles.formNote}>This preview is an introduction to your journey, not a booking. Experiences, services and your quote will be confirmed separately.</p>
    </fieldset>
  </form>;
}
