from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_LIBRARY_CSV = ROOT / "data" / "products" / "product_library.csv"
OUTPUT_JSON = ROOT / "data" / "products" / "products.normalized.json"


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\xa0", " ").strip()


def parse_list_field(value: Any) -> List[str]:
    text = clean_text(value)
    if not text:
        return []
    return [item.strip() for item in text.split(",") if item.strip()]


def split_itinerary_days(itinerary_text: str) -> List[Dict[str, Any]]:
    text = clean_text(itinerary_text)
    if not text:
        return []

    normalized = text.replace("\r\n", "\n")
    matches = list(re.finditer(r"Day\s+(\d+)\s*:\s*", normalized, flags=re.IGNORECASE))
    if not matches:
        return [{"day_number": 1, "raw_text": normalized, "activity_names": []}]

    days: List[Dict[str, Any]] = []
    for idx, match in enumerate(matches):
        day_number = int(match.group(1))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(normalized)
        raw_segment = normalized[start:end].strip()
        activity_names = [part.strip() for part in raw_segment.split("+") if part.strip()]
        days.append(
            {
                "day_number": day_number,
                "raw_text": raw_segment,
                "activity_names": activity_names,
            }
        )
    return days


def build_product_record(row: Dict[str, Any]) -> Dict[str, Any]:
    city = clean_text(row.get("城市 (City)"))
    product_id = clean_text(row.get("产品编号 (ProductID)"))
    product_name = clean_text(row.get("产品名称 (ProductName)"))
    duration_days = int(clean_text(row.get("行程天数 (Duration)")) or 0)
    regular_items = parse_list_field(row.get("常规项目 (Regular Items)"))
    optional_items = parse_list_field(row.get("可选项目 (Optional Items)"))
    regular_codes = parse_list_field(row.get("常规项目项目编号列表"))
    optional_codes = parse_list_field(row.get("可选项目项目编号列表"))
    itinerary_text = clean_text(row.get("每日行程 (Daily Itinerary)"))

    return {
        "product_id": product_id,
        "city": city,
        "product_name": product_name,
        "duration_days": duration_days,
        "itinerary_text": itinerary_text,
        "day_plans": split_itinerary_days(itinerary_text),
        "regular_items": regular_items,
        "optional_items": optional_items,
        "regular_item_codes": regular_codes,
        "optional_item_codes": optional_codes,
        "metadata": {
            "source": "data/products/product_library.csv",
            "raw_city": row.get("城市 (City)"),
            "raw_product_name": row.get("产品名称 (ProductName)"),
        },
    }


def main() -> None:
    with PRODUCT_LIBRARY_CSV.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f, quotechar='"', skipinitialspace=True)
        records = [build_product_record(row) for row in reader]

    payload = {
        "version": "1.0.0",
        "source": str(PRODUCT_LIBRARY_CSV.relative_to(ROOT)),
        "record_count": len(records),
        "products": records,
    }

    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(records)} products to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
