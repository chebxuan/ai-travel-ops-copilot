"use client";
import Image from "next/image";
import { useState } from "react";
import { heroPhoto } from "@/data/sitePhotography";
import Button from "./Button";
import Icon from "./Icon";
import styles from "./Home.module.css";

export default function HeroScene() {
  const [paused, setPaused] = useState(false);
  return <section className={styles.hero} aria-labelledby="hero-title">
    <div className={styles.heroBackground}><Image src={heroPhoto.src} alt={heroPhoto.alt} fill sizes="100vw" preload className={styles.movingPhoto} style={{ objectPosition: heroPhoto.position, animationPlayState: paused ? "paused" : "running" }} /></div>
    <div className={styles.heroShade} />
    <div className={`container ${styles.heroCopy}`}><p className="eyebrow">CHINA, BEYOND THE EXPECTED</p><h1 id="hero-title">A different view.<br /><em>A deeper connection.</em></h1><p className={styles.heroDescription}>Follow the river. Step into an old lane.<br />Find your own way into the stories of China.</p><div className={styles.heroActions}><Button href="#destinations" variant="light">Discover Destinations <Icon /></Button><Button href="/plan" variant="secondary">Let’s Plan Together <Icon /></Button></div></div>
    <div className={`container ${styles.sceneBar}`}><p className={styles.heroNote}>INTO THE MIST</p><button className={styles.motionToggle} type="button" onClick={() => setPaused((value) => !value)} aria-pressed={paused}>{paused ? "Resume motion" : "Pause motion"}</button></div>
  </section>;
}
