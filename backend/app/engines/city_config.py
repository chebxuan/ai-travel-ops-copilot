# city_config.py
# 城市配置管理模块
# 用于管理各城市的成本库路径、折扣规则、交通选择等配置

import os
from backend.app.core.paths import ROOT
from typing import Dict, Any, Optional


# 城市成本库文件映射
CITY_COST_FILES = {
    "北京": "data/products/services/mashes/北京_merged.csv",
    "上海": "data/products/services/mashes/上海_merged.csv",
    "广州": "data/products/services/mashes/广州_merged.csv",
    "重庆": "data/products/services/mashes/重庆_merged.csv",
    "西安": "data/products/services/mashes/西安_merged.csv",
    "阳朔": "data/products/services/mashes/阳朔_merged.csv",
    "张家界": "data/products/services/mashes/张家界_merged.csv",
    "贵州": "data/products/services/mashes/贵州_merged.csv",
    "云南": "data/products/services/mashes/云南_merged.csv",
    "成都": "data/products/services/mashes/成都_merged.csv",
}

# 城市代码前缀映射
CITY_CODE_PREFIX = {
    "北京": "BJ",
    "上海": "SH",
    "广州": "GZ",
    "重庆": "CQ",
    "西安": "XA",
    "阳朔": "YS",
    "张家界": "ZJJ",
    "贵州": "GUIZ",
    "云南": "YN",
    "成都": "CD",
}

# 各城市的儿童折扣规则
CHILD_DISCOUNT_RULES = {
    "北京": {
        "BJ-TICKET-05": 0.0,   # 故宫：1.2m以下免费
        "BJ-TICKET-04": 0.5,   # 慕田峪：儿童半价
        "BJ-TICKET-01": 0.5,   # 天坛：儿童半价
        "BJ-TICKET-08": 0.5,   # 颐和园：儿童半价
        "DEFAULT": 1.0,        # 默认：全价
    },
    "上海": {
        "SH-TICKET-07": 0.5,   # 迪士尼：儿童半价
        "DEFAULT": 1.0,
    },
    "广州": {
        "DEFAULT": 1.0,
    },
    # 可以为其他城市添加特定规则
}

# 各城市的老人折扣规则
SENIOR_DISCOUNT_RULES = {
    "北京": {
        "BJ-TICKET-05": 0.5,   # 故宫：老人半价
        "BJ-TICKET-04": 0.5,   # 慕田峪：老人半价
        "DEFAULT": 1.0,
    },
    "上海": {
        "SH-TICKET-07": 0.5,   # 迪士尼：老人半价
        "DEFAULT": 1.0,
    },
    "广州": {
        "DEFAULT": 1.0,
    },
}

# 各城市的交通选择规则
def get_transport_code_for_city(city: str, total_people: int) -> str:
    """
    根据城市和人数返回合适的交通工具代码
    """
    prefix = CITY_CODE_PREFIX.get(city, "BJ")

    # 默认规则：4人及以下用5座车，超过4人用7座车
    if total_people <= 4:
        return f"{prefix}-TRANS-01"  # 5座车
    else:
        return f"{prefix}-TRANS-02"  # 7座车


def get_child_discount_rules(city: str) -> Dict[str, float]:
    """获取指定城市的儿童折扣规则"""
    return CHILD_DISCOUNT_RULES.get(city, {"DEFAULT": 1.0})


def get_senior_discount_rules(city: str) -> Dict[str, float]:
    """获取指定城市的老人折扣规则"""
    return SENIOR_DISCOUNT_RULES.get(city, {"DEFAULT": 1.0})


def get_cost_file_path(city: str) -> Optional[str]:
    """获取指定城市的成本库文件路径"""
    relative_path = CITY_COST_FILES.get(city)
    if relative_path:
        # 相对于engines目录的路径
        return str(ROOT / relative_path)
    return None


def get_city_code_prefix(city: str) -> str:
    """获取城市代码前缀"""
    return CITY_CODE_PREFIX.get(city, "UNKNOWN")


def list_available_cities() -> list:
    """列出所有可用城市"""
    return list(CITY_COST_FILES.keys())
