import Link from "next/link";
import copy from "@/data/destination_copy.json";
import { cityName } from "@/data/products";
import Icon from "./Icon";
import DestinationPhoto from "./DestinationPhoto";
import styles from "./Home.module.css";

export default function DestinationCard({ destination }) {
  const href = `/plan?destination=${destination.slug}`;
  return <article className={styles.destinationCard} data-reveal>
    <div className={styles.cardImage}><DestinationPhoto slug={destination.slug} /><Link href={href} className={styles.imageLink} tabIndex={-1} aria-hidden="true" /></div>
    <div className={styles.cardBody}>
      <div className={styles.cardTitle}><h3><Link href={href}>{cityName(destination.name)}</Link></h3></div>
      <p className={styles.cardStory}>{copy[destination.slug].story}</p>
      <div className={styles.cardTags}>{copy[destination.slug].tags.map((tag) => <span key={tag} className="tag">{tag}</span>)}</div>
      <Link href={href} className={styles.cardLink} aria-label={`Explore ${cityName(destination.name)}`}>Begin Your Journey <Icon size={18} /></Link>
    </div>
  </article>;
}
