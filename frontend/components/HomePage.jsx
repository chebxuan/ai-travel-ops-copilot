import Button from "./Button";
import Icon from "./Icon";
import DestinationPhoto from "./DestinationPhoto";
import DestinationCatalog from "./DestinationCatalog";
import Reveal from "./Reveal";
import HeroScene from "./HeroScene";
import styles from "./Home.module.css";

export default function HomePage() {
  return <main id="main"><Reveal>
    <HeroScene />
    <div className="container"><section className={styles.editorialIntro} data-reveal><p className="eyebrow">PLACES. PEOPLE. EVERYDAY WONDER.</p><h2>Come for the landscape.<br /><em>Stay curious about the life within it.</em></h2><p>A morning in a hutong. Tea poured slowly in Chengdu. Stories held in silver, stone and timber. Our journeys bring China’s celebrated sights into conversation with its living traditions.</p></section><DestinationCatalog />
    <section className={styles.howItWorks} aria-labelledby="how-title" data-reveal><div><p className="eyebrow">YOUR CURIOSITY IS THE STARTING POINT</p><h2 className="section-title" id="how-title">Make room for your own story.</h2></div><div className={styles.steps}>{[{ title: "Find a place that draws you in", copy: "Start with a destination and the culture that makes it distinct." }, { title: "Discover what each day holds", copy: "Explore route stories, choose experiences and share your preferences." }, { title: "Talk it through with us", copy: "Send your journey or an idea. Your final arrangements and quote are confirmed with our team." }].map((step) => <div className={styles.step} key={step.title}><Icon name="compass" size={22} /><h3>{step.title}</h3><p>{step.copy}</p></div>)}</div></section>
    <section className={styles.customBanner} data-reveal><DestinationPhoto slug="beijing" /><div className={styles.bannerShade} /><div className={styles.bannerCopy}><p className="eyebrow">NO NEED TO HAVE IT ALL FIGURED OUT</p><h2>Where could your curiosity take you?</h2><p>Tell us a little about the journey you have in mind.</p><Button href="/plan" variant="light">Start a Conversation <Icon /></Button></div></section></div>
  </Reveal></main>;
}
