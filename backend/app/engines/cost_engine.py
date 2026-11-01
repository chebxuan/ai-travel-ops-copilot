# cost_engine.py
# 职责：基于产品编号列表 + 人数构成 + 用户偏好，计算总报价
# 输入：product Dict + user_intent Dict
# 输出：结构化报价明细 Dict（PricingResultJSON-aligned）

from __future__ import annotations

import csv
import math
from datetime import datetime
from typing import Any, Dict, List

from .city_config import (
    get_child_discount_rules,
    get_city_code_prefix,
    get_cost_file_path,
    get_senior_discount_rules,
    get_transport_code_for_city,
)


def parse_bool(value, default=True):
    """稳健解析布尔值"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "旺季", "是"}:
            return True
        if normalized in {"false", "0", "no", "n", "淡季", "否"}:
            return False
    return bool(value)


def parse_int(value, default=0, minimum=0):
    """稳健解析整数值，并应用最小值限制"""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(parsed, minimum)


def safe_float(value, default=0.0):
    """安全转换为 float，处理范围值和非数字"""
    if value is None:
        return default

    text = str(value).strip().strip('"')
    if not text:
        return default

    if "-" in text:
        try:
            parts = text.split("-")
            return (float(parts[0]) + float(parts[1])) / 2
        except Exception:
            return default

    if text in ["免费", "无固定单价", "需预约"]:
        return 0.0

    try:
        return float(text)
    except Exception:
        return default


def load_cost_db(csv_path=None, city=None):
    """
    读取成本库 CSV，返回以项目编号为 Key 的字典
    输出格式: {"BJ-TICKET-05": {"price": 40, "price_peak": 60, ...}}
    """
    from backend.app.storage.repository import database_enabled, dataset
    if csv_path is None and database_enabled():
        return dataset()['costs'].get(city or '北京', {})
    if csv_path is None:
        if city:
            csv_path = get_cost_file_path(city)
            if csv_path is None:
                print(f"[错误] 找不到城市 {city} 的成本库文件")
                return {}
        else:
            csv_path = get_cost_file_path("北京")

    db = {}
    try:
        with open(csv_path, newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = (row.get('项目编号') or '').strip()
                if not code:
                    continue

                price = safe_float(row.get('单价'), 0.0)
                price_peak_raw = row.get('单价（旺季）', '')
                price_peak = safe_float(price_peak_raw, 0.0)
                if not price_peak_raw or not str(price_peak_raw).strip():
                    price_peak = price

                db[code] = {
                    "name": (row.get('项目名称') or '').strip(),
                    "category": (row.get('服务类目') or '').strip(),
                    "price": price,
                    "price_peak": price_peak,
                    "unit": (row.get('单位') or '').strip(),
                    "note": (row.get('项目备注') or '').strip(),
                }
    except FileNotFoundError:
        print(f"[错误] 找不到成本库文件: {csv_path}")
    except Exception as e:
        print(f"[错误] 读取成本库文件时出错: {str(e)}")
    return db


def get_effective_price(item, is_peak):
    """获取项目在当前季节的有效价格"""
    if is_peak and item.get('price_peak', 0) > 0:
        return item['price_peak']
    return item.get('price', 0)


def get_required_item(db, code, missing_codes, field_name):
    """按 code 从成本库获取项目，不存在时记录错误"""
    if not code:
        return None
    item = db.get(code)
    if item is None:
        missing_codes.append({"field": field_name, "code": code})
        return None
    return item


def parse_code_list(raw_codes):
    """解析项目编号列表，兼容字符串或 list"""
    if raw_codes is None:
        return []
    if isinstance(raw_codes, list):
        return [str(code).strip() for code in raw_codes if str(code).strip()]
    return [c.strip() for c in str(raw_codes).split(',') if c.strip()]


def get_product_regular_codes(product):
    return parse_code_list(
        product.get('常规项目项目编号列表', product.get('regular_item_codes', []))
    )


def get_product_optional_codes(product):
    return parse_code_list(
        product.get('可选项目项目编号列表', product.get('optional_item_codes', []))
    )


def validate_selected_optional_codes(product, selected_optional_codes):
    """校验已选可选项目是否属于当前产品"""
    allowed_optional_codes = set(get_product_optional_codes(product))
    return [code for code in selected_optional_codes if code not in allowed_optional_codes]


def get_item_price(code, is_peak, city="北京"):
    """获取单个项目的适用单价"""
    db = load_cost_db(city=city)
    if code not in db:
        return 0, "未知项目"
    item = db[code]
    return get_effective_price(item, is_peak), item['name']


def calc_ticket_activity_cost(item_codes, adults, children, seniors, is_peak, city="北京", missing_codes=None):
    """
    计算门票+活动的总成本
    返回：{
        "breakdown": [每项明细],
        "subtotal": 小计
    }
    """
    db = load_cost_db(city=city)
    child_discount = get_child_discount_rules(city)
    senior_discount = get_senior_discount_rules(city)

    if missing_codes is None:
        missing_codes = []

    breakdown = []
    subtotal = 0.0

    for code in item_codes:
        normalized_code = code.strip()
        item = get_required_item(db, normalized_code, missing_codes, "item")
        if item is None:
            continue

        unit_price = get_effective_price(item, is_peak)
        child_rate = child_discount.get(normalized_code, child_discount["DEFAULT"])
        senior_rate = senior_discount.get(normalized_code, senior_discount["DEFAULT"])

        adult_cost = unit_price * adults
        child_cost = unit_price * child_rate * children
        senior_cost = unit_price * senior_rate * seniors
        line_total = adult_cost + child_cost + senior_cost
        subtotal += line_total

        breakdown.append(
            {
                "code": normalized_code,
                "name": item['name'],
                "unit": item.get('unit') or "person",
                "unit_price": round(unit_price, 2),
                "adults": adults,
                "children": children,
                "seniors": seniors,
                "adult_subtotal": round(adult_cost, 2),
                "child_subtotal": round(child_cost, 2),
                "senior_subtotal": round(senior_cost, 2),
                "line_total": round(line_total, 2),
                "note": item['note'],
                "category": item.get('category', ''),
            }
        )

    return {"breakdown": breakdown, "subtotal": round(subtotal, 2)}


def calc_hotel_cost(hotel_code, total_people, hotel_nights, city="北京", is_peak=False, missing_codes=None):
    """计算酒店成本：房间数 = ceil(总人数 / 2)，住宿晚数来自问卷输入"""
    if missing_codes is None:
        missing_codes = []

    if not hotel_code or hotel_nights <= 0:
        return {
            "hotel_code": hotel_code,
            "hotel_name": None,
            "hotel_price": 0,
            "rooms": 0,
            "nights": hotel_nights,
            "subtotal": 0,
            "unit": "room_night",
            "note": "",
        }

    db = load_cost_db(city=city)
    item = get_required_item(db, hotel_code, missing_codes, "hotel")
    if item is None:
        return {
            "hotel_code": hotel_code,
            "hotel_name": None,
            "hotel_price": 0,
            "rooms": 0,
            "nights": hotel_nights,
            "subtotal": 0,
            "unit": "room_night",
            "note": "",
        }

    rooms = math.ceil(total_people / 2)
    hotel_price = get_effective_price(item, is_peak)
    total = hotel_price * rooms * hotel_nights

    return {
        "hotel_code": hotel_code,
        "hotel_name": item['name'],
        "hotel_price": round(hotel_price, 2),
        "rooms": rooms,
        "nights": hotel_nights,
        "subtotal": round(total, 2),
        "unit": item.get('unit') or "room_night",
        "note": item.get('note', ''),
    }


def calc_transport_cost(total_people, car_days, transfer_code, transfer_times, city="北京", is_peak=False, missing_codes=None):
    """计算交通成本：包车 + 接送，天数和次数都来自显式输入"""
    if missing_codes is None:
        missing_codes = []

    db = load_cost_db(city=city)

    car_code = None
    car_name = None
    car_daily_price = 0
    car_subtotal = 0
    car_note = ""
    if car_days > 0:
        car_code = get_transport_code_for_city(city, total_people)
        car_item = get_required_item(db, car_code, missing_codes, "car")
        if car_item is not None:
            car_name = car_item.get('name')
            car_daily_price = get_effective_price(car_item, is_peak)
            car_subtotal = round(car_daily_price * car_days, 2)
            car_note = car_item.get('note', '')

    transfer_name = None
    transfer_price = 0
    transfer_subtotal = 0
    transfer_note = ""
    if transfer_code and transfer_times > 0:
        transfer_item = get_required_item(db, transfer_code, missing_codes, "transfer")
        if transfer_item is not None:
            transfer_name = transfer_item.get('name')
            transfer_price = get_effective_price(transfer_item, is_peak)
            transfer_subtotal = round(transfer_price * transfer_times, 2)
            transfer_note = transfer_item.get('note', '')

    return {
        "car_code": car_code,
        "car_name": car_name,
        "car_daily_price": round(car_daily_price, 2),
        "car_days": car_days,
        "car_subtotal": car_subtotal,
        "car_note": car_note,
        "transfer_code": transfer_code,
        "transfer_name": transfer_name,
        "transfer_price": round(transfer_price, 2),
        "transfer_times": transfer_times,
        "transfer_subtotal": transfer_subtotal,
        "transfer_note": transfer_note,
        "subtotal": round(car_subtotal + transfer_subtotal, 2),
    }


def calc_guide_cost(guide_code, days, city="北京", is_peak=False, missing_codes=None):
    """计算导游成本"""
    if missing_codes is None:
        missing_codes = []

    db = load_cost_db(city=city)
    if not guide_code:
        return {
            "guide_code": None,
            "guide_name": None,
            "daily_price": 0,
            "days": days,
            "subtotal": 0,
            "unit": "day",
            "note": "",
        }

    item = get_required_item(db, guide_code, missing_codes, "guide")
    if item is None:
        return {
            "guide_code": guide_code,
            "guide_name": None,
            "daily_price": 0,
            "days": days,
            "subtotal": 0,
            "unit": "day",
            "note": "",
        }

    price = get_effective_price(item, is_peak)
    total = price * days
    return {
        "guide_code": guide_code,
        "guide_name": item.get('name', '英文导游'),
        "daily_price": round(price, 2),
        "days": days,
        "subtotal": round(total, 2),
        "unit": item.get('unit') or "day",
        "note": item.get('note', ''),
    }


def build_validation_issues(invalid_optional_codes, missing_codes):
    issues = []

    if invalid_optional_codes:
        issues.append(
            {
                "field": "selected_optional_item_codes",
                "code": None,
                "codes": invalid_optional_codes,
                "message": "存在不属于当前产品的可选项目编号",
                "severity": "error",
            }
        )

    # 只报告真正缺失的项目，不报告价格为0或空的项目
    if missing_codes:
        # 过滤掉价格为0或空的项目
        critical_missing_codes = []
        for entry in missing_codes:
            code = entry.get("code")
            if code:
                # 检查是否是价格问题而不是完全缺失
                db = load_cost_db(entry.get("field", "北京"))
                item = db.get(code)
                if item and item.get('price', 0) == 0 and item.get('price_peak', 0) == 0:
                    # 价格为0，视为免费，不报错
                    continue
                critical_missing_codes.append(entry)

        if critical_missing_codes:
            missing_code_values = [entry.get("code") for entry in critical_missing_codes if entry.get("code")]
            issues.append(
                {
                    "field": "cost_lookup",
                    "code": None,
                    "codes": missing_code_values,
                    "message": "部分成本项目未在对应城市成本库中找到或价格配置异常",
                    "severity": "error",
                }
            )

    return issues


def build_ticket_line_items(ticket_result):
    line_items = []
    for row in ticket_result.get("breakdown", []):
        quantity = row.get("adults", 0) + row.get("children", 0) + row.get("seniors", 0)
        line_items.append(
            {
                "category": "ticket_activity",
                "code": row.get("code"),
                "name": row.get("name", ""),
                "unit": row.get("unit") or "person",
                "unit_price": round(row.get("unit_price", 0), 2),
                "quantity": float(quantity),
                "subtotal": round(row.get("line_total", 0), 2),
                "notes": [note for note in [row.get("note")] if note],
                "metadata": {
                    "adults": row.get("adults", 0),
                    "children": row.get("children", 0),
                    "seniors": row.get("seniors", 0),
                    "adult_subtotal": row.get("adult_subtotal", 0),
                    "child_subtotal": row.get("child_subtotal", 0),
                    "senior_subtotal": row.get("senior_subtotal", 0),
                    "service_category": row.get("category", ""),
                },
            }
        )
    return line_items


def build_hotel_line_items(hotel_result):
    if hotel_result.get("subtotal", 0) <= 0:
        return []

    quantity = float(hotel_result.get("rooms", 0) * hotel_result.get("nights", 0))
    return [
        {
            "category": "hotel",
            "code": hotel_result.get("hotel_code"),
            "name": hotel_result.get("hotel_name") or "Hotel",
            "unit": hotel_result.get("unit") or "room_night",
            "unit_price": round(hotel_result.get("hotel_price", 0), 2),
            "quantity": quantity,
            "subtotal": round(hotel_result.get("subtotal", 0), 2),
            "notes": [note for note in [hotel_result.get("note")] if note],
            "metadata": {
                "rooms": hotel_result.get("rooms", 0),
                "nights": hotel_result.get("nights", 0),
            },
        }
    ]


def build_transport_line_items(transport_result):
    line_items = []

    if transport_result.get("car_subtotal", 0) > 0:
        line_items.append(
            {
                "category": "transport",
                "code": transport_result.get("car_code"),
                "name": transport_result.get("car_name") or "Private Car",
                "unit": "day",
                "unit_price": round(transport_result.get("car_daily_price", 0), 2),
                "quantity": float(transport_result.get("car_days", 0)),
                "subtotal": round(transport_result.get("car_subtotal", 0), 2),
                "notes": [note for note in [transport_result.get("car_note")] if note],
                "metadata": {},
            }
        )

    if transport_result.get("transfer_subtotal", 0) > 0:
        line_items.append(
            {
                "category": "transport",
                "code": transport_result.get("transfer_code"),
                "name": transport_result.get("transfer_name") or "Transfer",
                "unit": "time",
                "unit_price": round(transport_result.get("transfer_price", 0), 2),
                "quantity": float(transport_result.get("transfer_times", 0)),
                "subtotal": round(transport_result.get("transfer_subtotal", 0), 2),
                "notes": [note for note in [transport_result.get("transfer_note")] if note],
                "metadata": {},
            }
        )

    return line_items


def build_guide_line_items(guide_result):
    if guide_result.get("subtotal", 0) <= 0:
        return []

    return [
        {
            "category": "guide",
            "code": guide_result.get("guide_code"),
            "name": guide_result.get("guide_name") or "Guide",
            "unit": guide_result.get("unit") or "day",
            "unit_price": round(guide_result.get("daily_price", 0), 2),
            "quantity": float(guide_result.get("days", 0)),
            "subtotal": round(guide_result.get("subtotal", 0), 2),
            "notes": [note for note in [guide_result.get("note")] if note],
            "metadata": {},
        }
    ]


def calculate_total_cost(product, user_intent):
    """
    主函数：汇总所有成本
    输入:
        product     ← services/travel_catalog.py 的产品记录
        user_intent ← services/travel_catalog.py 汇总的已校验条件
    输出:
        PricingResultJSON-aligned Dict
    """
    city = product.get('city', user_intent.get('city', '北京'))

    adults = parse_int(user_intent.get('adults', 2), default=2, minimum=1)
    children = parse_int(user_intent.get('children', 0), default=0, minimum=0)
    seniors = parse_int(user_intent.get('seniors', 0), default=0, minimum=0)
    total_people = adults + children + seniors

    days = parse_int(
        product.get('days', product.get('duration_days', user_intent.get('days', 1))),
        default=1,
        minimum=1,
    )
    is_peak = parse_bool(user_intent.get('is_peak', True), default=True)
    guide_code = user_intent.get('guide')

    city_code = get_city_code_prefix(city)
    default_hotel = f"{city_code}-HOTEL-01" if city_code else None
    hotel_code = user_intent.get('hotel', default_hotel)
    hotel_nights = parse_int(
        user_intent.get('hotel_nights', max(days - 1, 0)),
        default=max(days - 1, 0),
        minimum=0,
    )
    transfer_code = user_intent.get('transfer')
    transfer_times = parse_int(user_intent.get('transfer_times', 0), default=0, minimum=0)
    car_days = parse_int(user_intent.get('car_days', days), default=days, minimum=0)

    # 尊重 need_private_car 标志：如果显式设为 false，则取消包车
    need_private_car = user_intent.get('need_private_car', True)
    if isinstance(need_private_car, bool) and not need_private_car:
        car_days = 0

    # 同理：need_guide=false 时清除导游代码，不配导游
    need_guide = user_intent.get('need_guide', False)
    if isinstance(need_guide, bool) and not need_guide:
        guide_code = None

    regular_codes = get_product_regular_codes(product)
    selected_optional_codes = parse_code_list(user_intent.get('selected_optional', []))

    invalid_optional_codes = validate_selected_optional_codes(product, selected_optional_codes)
    missing_codes = []
    all_item_codes = regular_codes + selected_optional_codes

    ticket_result = calc_ticket_activity_cost(
        all_item_codes, adults, children, seniors, is_peak, city, missing_codes
    )
    hotel_result = calc_hotel_cost(
        hotel_code, total_people, hotel_nights, city, is_peak, missing_codes
    )
    transport_result = calc_transport_cost(
        total_people, car_days, transfer_code, transfer_times, city, is_peak, missing_codes
    )
    guide_days = parse_int(user_intent.get('guide_days', days), default=days, minimum=0)
    guide_result = calc_guide_cost(guide_code, guide_days, city, is_peak, missing_codes)

    validation_issues = build_validation_issues(invalid_optional_codes, missing_codes)

    # 只在真正缺失项目时才视为失败，价格问题视为免费
    critical_issues = [issue for issue in validation_issues if issue.get("severity") == "error"]
    success = len(critical_issues) == 0

    line_items = []
    line_items.extend(build_ticket_line_items(ticket_result))
    line_items.extend(build_hotel_line_items(hotel_result))
    line_items.extend(build_transport_line_items(transport_result))
    line_items.extend(build_guide_line_items(guide_result))

    category_subtotals = {
        "ticket_activity": round(ticket_result.get("subtotal", 0), 2),
        "hotel": round(hotel_result.get("subtotal", 0), 2),
        "transport": round(transport_result.get("subtotal", 0), 2),
        "guide": round(guide_result.get("subtotal", 0), 2),
        "other": 0.0,
    }

    grand_total = round(sum(category_subtotals.values()), 2)
    selected_product_id = product.get("product_id") or product.get("产品编号 (ProductID)")

    result = {
        "lead_id": user_intent.get("lead_id"),
        "selected_product_id": selected_product_id,
        "success": success,
        "summary": {
            "city": city,
            "product_name": product.get('product_name', product.get('产品名称 (ProductName)', '')),
            "days": days,
            "total_people": total_people,
            "adults": adults,
            "children": children,
            "seniors": seniors,
            "is_peak": is_peak,
            "hotel_nights": hotel_nights,
            "car_days": car_days,
            "transfer_times": transfer_times,
            "grand_total": grand_total,
            "per_person": round(grand_total / max(total_people, 1), 2),
            "currency": "RMB",
        },
        "line_items": line_items,
        "category_subtotals": category_subtotals,
        "regular_item_codes": regular_codes,
        "selected_optional_item_codes": selected_optional_codes,
        "validation_issues": validation_issues,
        "error": None if success else "成本计算失败：产品库与成本库存在未对齐的项目编号",
        "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        # backward-compatible fields for current callers/tests
        "ticket_activity": ticket_result,
        "hotel": hotel_result,
        "transport": transport_result,
        "guide": guide_result,
        "regular_items": regular_codes,
        "selected_optional_items": selected_optional_codes,
        "validation_errors": validation_issues,
    }

    return result
