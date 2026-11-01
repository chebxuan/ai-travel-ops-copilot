import records from "./products.json";
import { destinations } from "./destinations";
import labels from "./product_labels.json";

export const products = records.map((product) => ({ ...product, englishTitle: labels.product_titles[product.id], theme: destinations.find((destination) => destination.name === product.city)?.artTheme || "city" }));
export const cityName = (city) => labels.city_names[city] || city;
export const optionalName = (name) => labels.optional_labels[name]?.name || name;
export const productCities = destinations.map((destination) => destination.name);
export function availableDurations(city) {
  return [...new Set(products.filter((product) => product.city === city).map((product) => product.days))].sort((a, b) => a - b);
}
