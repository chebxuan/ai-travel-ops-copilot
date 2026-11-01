import Image from "next/image";
import { destinationPhotos } from "@/data/sitePhotography";
import styles from "./Photography.module.css";
export default function DestinationPhoto({ slug, priority = false, sizes = "(max-width: 600px) 100vw, (max-width: 900px) 50vw, 33vw" }) {
  const photo = destinationPhotos[slug] || destinationPhotos.yangshuo;
  return <div className={styles.photo}><Image src={photo.src} alt={photo.alt} fill sizes={sizes} preload={priority} className={styles.image} style={{ objectPosition: photo.position }} /></div>;
}
