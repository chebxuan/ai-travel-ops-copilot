"use client";
import { useState } from "react";
import { destinations, destinationThemes } from "@/data/destinations";
import DestinationCard from "./DestinationCard";
import styles from "./Home.module.css";

const themeLabels = { "全部目的地": "All Destinations", "历史文脉": "History & Heritage", "城市生活": "City Life", "山水人文": "Landscapes & Culture", "民族风情": "Living Traditions" };

export default function DestinationCatalog() {
  const [theme, setTheme] = useState("全部目的地");
  const visibleDestinations = destinations.filter((destination) => theme === "全部目的地" || destination.themes.includes(theme));
  return <section className={styles.catalog} id="destinations" aria-labelledby="destinations-title">
    <div className={styles.sectionHeading} id="journeys"><div><p className="eyebrow">PLACES WITH A STORY</p><h2 id="destinations-title" className="section-title">Every place has a story.</h2></div><p className="section-copy">Discover a place through its everyday life<br />and the culture that shapes it.</p></div>
    <div className={styles.cityFilters} role="group" aria-label="Filter destinations by theme">{["全部目的地", ...destinationThemes].map((name) => <button key={name} type="button" aria-pressed={theme === name} className={theme === name ? styles.filterActive : ""} onClick={() => setTheme(name)}>{themeLabels[name]}</button>)}</div>
    <p className={styles.catalogNote} aria-live="polite">{visibleDestinations.length} destinations. Different ways to discover local life.</p>
    <div className={styles.destinationsGrid}>{visibleDestinations.map((destination) => <DestinationCard key={destination.slug} destination={destination} />)}</div>
  </section>;
}
