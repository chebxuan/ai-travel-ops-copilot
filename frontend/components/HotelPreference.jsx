import styles from "./Planner.module.css";
export const hotelLabels = { discuss: "I’d like your recommendations", arrange: "Please arrange hotels for me", self_booked: "I’ll arrange my own hotels" };
export default function HotelPreference({ value, onChange, id = "trip-hotel" }) {
  return <label className={styles.field} htmlFor={id}><span>Accommodation</span><select id={id} name="hotelPreference" value={value} onChange={onChange}>{Object.entries(hotelLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select><small>Hotel preferences are saved with your enquiry. Accommodation is quoted separately.</small></label>;
}
