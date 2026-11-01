"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import Icon from "./Icon";
import styles from "./SiteShell.module.css";

export default function SiteHeader() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const isPlan = pathname === "/plan";
  return <header className={`${styles.header} ${pathname === "/" ? styles.headerHome : ""}`}><div className={`container ${styles.headerInner}`}>
    <Link href="/" className={styles.brand} onClick={() => setOpen(false)} aria-label="Travel Copilot, home"><span className={styles.mark}><Icon name="compass" size={28} /></span><span><strong>Travel Copilot</strong><small>CHINA, YOUR WAY</small></span></Link>
    <button className={styles.menuButton} type="button" onClick={() => setOpen(!open)} aria-expanded={open} aria-controls="site-nav" aria-label={open ? "Close navigation" : "Open navigation"}><Icon name={open ? "close" : "menu"} /></button>
    <nav id="site-nav" className={`${styles.nav} ${open ? styles.navOpen : ""}`} aria-label="Main navigation">
      <Link href="/" aria-current={!isPlan ? "page" : undefined} onClick={() => setOpen(false)}>Explore</Link>
      <Link href="/#destinations" onClick={() => setOpen(false)}>Destinations</Link>
      <Link href="/plan" aria-current={isPlan ? "page" : undefined} onClick={() => setOpen(false)}>Contact Us</Link>
    </nav>
    <Link href="/plan" className={styles.headerCta} onClick={() => setOpen(false)}>Let’s Talk <Icon size={16} /></Link>
  </div></header>;
}
