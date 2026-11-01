import { Suspense } from "react";
import Link from "next/link";
import TravelPlanner from "@/components/TravelPlanner";
import Icon from "@/components/Icon";
import styles from "@/components/Planner.module.css";

export const metadata = { title: "Start Your China Journey" };

export default function PlanPage() {
  return <main id="main" className={`container ${styles.planPage}`}><Link href="/#journeys" className={styles.backLink}><Icon size={16} />Back to destinations</Link><Suspense fallback={<div className={styles.routeLoading}>Opening your journey planner…</div>}><TravelPlanner /></Suspense></main>;
}
