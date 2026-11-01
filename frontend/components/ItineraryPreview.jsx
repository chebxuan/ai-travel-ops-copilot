import Link from "next/link";
import Icon from "./Icon";
import DestinationPhoto from "./DestinationPhoto";
import SalesQuote from "./SalesQuote";
import JourneyEnquiry from "./JourneyEnquiry";
import { destinations } from "@/data/destinations";
import styles from "./Planner.module.css";

function Highlights({ items }) {
  return items.length > 0 && <div className={styles.menuHighlights}>{items.map((item) => <div key={item.name}><h4>{item.name}</h4><p>{item.description}</p></div>)}</div>;
}

function Story({ story, route }) {
  const branches = route ? story.alternatives.filter((branch) => branch.choice === route.choice) : story.alternatives;
  return <><p className={styles.routeStory}>{story.description}</p><Highlights items={story.highlights} />{branches.length > 0 && <div className={styles.menuAlternatives}><p className={styles.choiceNote}>{route ? "Your selected direction" : "Choose one of these two directions to receive a route-specific estimate."}</p>{branches.map((branch) => <div key={branch.title}><h4>{branch.title}</h4><p className={styles.routeStory}>{branch.description}</p><Highlights items={branch.highlights} /></div>)}</div>}</>;
}

export default function ItineraryPreview({ result, status, dirty, error, onEnquiryBusyChange }) {
  const product = result?.product;
  const menu = product?.menu;
  const photoSlug = destinations.find((destination) => destination.name === product?.city)?.slug || "yangshuo";
  return <section className={styles.previewCard} aria-labelledby="preview-heading" aria-busy={status === "loading"}>
    <div className={styles.previewHeading}><div><span className={styles.stepNumber}>02</span><h2 id="preview-heading">Your Journey, Inspired</h2></div><span className="tag">Journey menu</span></div>
    <div className={styles.statusMessage} role="status">{status === "loading" ? "Preparing your journey…" : dirty ? "Your choices have changed. Preview again to update your journey." : status === "success" ? "Your journey preview is ready." : ""}</div>
    {status === "loading" ? <div className={styles.emptyPreview}><div className={styles.loadingCompass}><Icon name="compass" size={54} /></div><h3>A journey is taking shape.</h3><p>Bringing your route and experiences together.</p></div> : status === "error" ? <div className={styles.emptyPreview}><Icon name="compass" size={48} /><h3>We could not prepare your preview.</h3><p>{error}</p><p>Your choices are saved. Please try again.</p></div> : status === "empty" ? <div className={styles.emptyPreview}><Icon name="compass" size={48} /><h3>Explore another possibility.</h3><p>There is no standard journey for this destination and duration.</p><Link className="button button--secondary" href="/#journeys">Explore destinations <Icon size={18} /></Link></div> : !result ? <div className={styles.emptyPreview}><div className={styles.emptyArt}><DestinationPhoto slug="yangshuo" /></div><p className="eyebrow">YOUR NEXT STORY STARTS HERE</p><h3>A new chapter awaits.</h3><p>Choose your destination and experiences.<br />Discover what each day could hold.</p></div> : <div className={styles.previewContent}>
      {dirty && <div className={styles.staleNotice}><Icon name="calendar" size={18} /><p>This preview reflects your previous choices. Preview again to refresh it.</p></div>}
      <div className={styles.resultHero}><DestinationPhoto slug={photoSlug} /><div><p>{menu.city_name} · {product.days} DAYS</p><h3>{menu.title}</h3></div></div>
      <div className={styles.resultSummary}><span><Icon name="calendar" size={17} />{product.days} days</span><span><Icon name="people" size={17} />{Number(result.request.adults) + Number(result.request.children) + Number(result.request.seniors)} travellers</span>{result.request.date && <span>{result.request.date}</span>}</div>
      <SalesQuote quote={result.quote} dirty={dirty} />
      <p className={styles.menuIntro}>{menu.introduction}</p>
      {menu.notice && <div className={styles.staleNotice}><Icon name="calendar" size={18} /><p>{menu.notice}</p></div>}
      <div className={styles.menuDays}>{menu.days.map((day) => <article className={styles.menuDay} key={day.day}><div className={styles.menuDayHeading}><span className={styles.dayNumber}>{String(day.day).padStart(2, "0")}</span><div><p className="eyebrow">DAY {day.day}</p><h3>{day.title}</h3></div></div><Story story={day} route={result.route?.day === day.day ? result.route : null} /></article>)}</div>
      {menu.overview.length > 0 && <div className={styles.menuDays}><p className="eyebrow">JOURNEY CHAPTERS · DAY-BY-DAY DETAILS TO BE CONFIRMED</p>{menu.overview.map((chapter) => <article className={styles.menuDay} key={chapter.title}><h3>{chapter.title}</h3><Story story={chapter} /></article>)}</div>}
      {result.experiences.length > 0 && <section className={styles.selectedExperiences} aria-labelledby="experiences-heading"><p className="eyebrow">A LITTLE MORE OF WHAT YOU LOVE</p><h3 id="experiences-heading">Your Selected Experiences</h3><p>Personal touches to make this journey your own.</p>{result.experiences.map((experience) => <article className={styles.experienceCard} key={experience.name}><div><Icon name="leaf" size={20} /><h4>{experience.name}</h4></div><p>{experience.description}</p>{experience.duration && <small>Approx. {experience.duration}</small>}<span className="tag">{result.quote?.status === "estimated" && !dirty ? "Selected · Included in your estimate" : "Selected · Quote to be confirmed"}</span></article>)}</section>}
      <div className={styles.serviceSummary}><h3>Your Travel Preferences</h3><p>{[result.guideLabel || "Standard English-speaking guide to be confirmed", result.request.car ? "Private vehicle requested" : "No private vehicle requested"].join(" · ")}</p>{result.route && <p>Day {result.route.day}: {result.route.label}</p>}<p>Accommodation is not included in this price. If you would like help arranging your stay, please contact our team.</p><small>Availability and final arrangements will be confirmed separately.</small></div>
      {result.request.notes && <div className={styles.notesSummary}><h3>Your Ideas</h3><p>{result.request.notes}</p></div>}
      <p className={styles.resultNote}>An inspiring preview. Your final itinerary, reservations, selected experiences and quote will be confirmed separately.</p>
    </div>}
    <JourneyEnquiry result={result} visible={status === "success"} dirty={dirty} onBusyChange={onEnquiryBusyChange} />
  </section>;
}
