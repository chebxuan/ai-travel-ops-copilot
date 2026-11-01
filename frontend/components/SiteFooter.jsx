import Link from "next/link";
import { destinationPhotos, heroPhoto } from "@/data/sitePhotography";
import Icon from "./Icon";
import styles from "./SiteShell.module.css";
export default function SiteFooter() {
  return <footer className={styles.footer}><div className={`container ${styles.footerInner}`}><div className={styles.footerBrand}><Icon name="compass" size={24} /><strong>Travel Copilot</strong><span>Make room for discovery.</span></div><div className={styles.footerLinks}><Link href="/#journeys">Explore</Link><Link href="/plan">Contact Us</Link></div><p className={styles.footerNote}>PUBLIC SOURCE DEMO: synthetic prices, example routes and original placeholder art. No real booking or supplier offer.</p><details id="photography" className={styles.photoCredits}><summary>Demo artwork</summary><p>Original SVG placeholder illustrations. Production photographs are excluded from this public repository.</p><ul>{[...Object.values(destinationPhotos), heroPhoto].map((photo) => <li key={photo.src}><a href={photo.src} target="_blank" rel="noreferrer">{photo.alt}</a></li>)}</ul></details></div></footer>;
}
