"""非结构化行情通知本地规则解析器。"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass
class ParsedMarketSignal:
    brand: str | None = None
    category: str | None = None
    mpn: str | None = None
    series: str | None = None
    event_type: str = "other"
    increase_min_pct: float | None = None
    increase_max_pct: float | None = None
    lead_time_weeks: int | None = None
    shortage_confirmed: bool = False
    effective_date_text: str | None = None
    confidence: float = 0.0
    confidence_reason: str = ""
    evidence_text: str = ""
    review_status: str = "observation"

    def to_dict(self) -> dict:
        return {
            "brand": self.brand,
            "category": self.category,
            "mpn": self.mpn,
            "series": self.series,
            "event_type": self.event_type,
            "increase_min_pct": self.increase_min_pct,
            "increase_max_pct": self.increase_max_pct,
            "lead_time_weeks": self.lead_time_weeks,
            "shortage_confirmed": self.shortage_confirmed,
            "effective_date_text": self.effective_date_text,
            "confidence": self.confidence,
            "confidence_reason": self.confidence_reason,
            "evidence_text": self.evidence_text,
            "review_status": self.review_status,
        }


BRANDS = [
    # 被动元件/MLCC
    "TDK", "Murata", "村田", "Samsung", "三星电机", "SEMCO",
    "Yageo", "国巨", "风华", "华新科", "太阳诱电", "Taiyo",
    "AVX", "KEMET", "基美",
    # MCU/处理器
    "ST", "意法半导体", "TI", "德州仪器", "NXP", "恩智浦",
    "Microchip", "微芯", "Renesas", "瑞萨",
    "GD", "兆易创新", "GigaDevice",
    # 功率器件/IGBT/MOSFET
    "Infineon", "英飞凌", "三菱", "Mitsubishi", "赛米控", "Semikron",
    "ON", "Onsemi", "安森美", "Vishay", "威世",
    "斯达半导", "士兰微", "华润微", "东微半导", "新洁能",
    # 国产分立器件
    "长晶", "Changjing", "杨杰", "Yangjie", "乐山无线电", "LRC",
    # 存储
    "美光", "Micron", "SK海力士", "SK Hynix", "长鑫存储", "CXMT",
    "华邦", "Winbond", "旺宏", "Macronix",
    # 连接器
    "Omron", "Panasonic", "松下", "JST", "TE", "Molex",
    "Amphenol", "安费诺", "Hirose", "广濑",
    # PCB/基板
    "日东纺", "Nitto Boseki", "深南电路", "景旺电子",
    # 晶振
    "EPSON", "爱普生", "NDK", "TXC", "台湾晶技",
    # 其他半导体
    "ADI", "Analog Devices", "亚德诺", "Maxim", "美信",
    "ROHM", "罗姆", "Toshiba", "东芝",
    "Intel", "AMD", "英伟达", "NVIDIA",
]

RUMOR_WORDS = ["据说", "传闻", "可能", "群里说", "朋友圈", "听说"]
SHORTAGE_WORDS = ["缺货", "紧缺", "供需紧张", "allocation", "shortage", "产能不足"]
PRICE_WORDS = ["涨价", "价格上调", "price increase", "price adjustment", "increase"]


def parse_market_notice(raw_text: str, title: str = "", source_type: str = "manual", source_name: str = "") -> list[ParsedMarketSignal]:
    text = " ".join(part for part in [title or "", raw_text or ""] if part).strip()
    if not text:
        return []

    brand = _extract_brand(text, source_name)
    category = _extract_category(text)
    mpn = _extract_mpn(text)
    increase_min, increase_max = _extract_price_increase(text)
    lead_time = _extract_lead_time(text)
    shortage = _contains_any(text, SHORTAGE_WORDS)
    event_type = _event_type(text, increase_max, lead_time, shortage)

    confidence, reason = _score_confidence(
        source_type=source_type,
        brand=brand,
        category=category,
        mpn=mpn,
        increase_max=increase_max,
        lead_time=lead_time,
        shortage=shortage,
        text=text,
    )
    review_status = _review_status(confidence, text)

    if not any([brand, category, mpn, increase_max, lead_time, shortage, _contains_any(text, PRICE_WORDS)]):
        return []

    return [ParsedMarketSignal(
        brand=brand,
        category=category,
        mpn=mpn,
        series=_extract_series(mpn),
        event_type=event_type,
        increase_min_pct=increase_min,
        increase_max_pct=increase_max,
        lead_time_weeks=lead_time,
        shortage_confirmed=shortage,
        effective_date_text=_extract_effective_date(text),
        confidence=confidence,
        confidence_reason=reason,
        evidence_text=text[:500],
        review_status=review_status,
    )]


def _extract_brand(text: str, source_name: str = "") -> str | None:
    combined = f"{source_name or ''} {text}"
    combined_lower = combined.lower()
    for brand in BRANDS:
        if brand.lower() in combined_lower:
            return brand
    return None


def _extract_category(text: str) -> str | None:
    compact = text.replace(" ", "").lower()

    # 电容类
    if "高容mlcc" in compact or ("mlcc" in compact and any(token in compact for token in ["高容", "大容", "10uf", "22uf", "47uf"])):
        return "high_cap_mlcc"
    if "mlcc" in compact or "瓷介电容" in compact or "陶瓷电容" in compact or "贴片电容" in compact:
        return "MLCC"
    if "薄膜电容" in compact or "filmcapacitor" in compact or "filmcap" in compact:
        return "film_capacitor"
    if "安规电容" in compact or "safetycapacitor" in compact or "x2电容" in compact or "y2电容" in compact:
        return "safety_capacitor"
    if "电解电容" in compact or "铝电解" in compact:
        return "aluminum_electrolytic_capacitor"
    if "钽电容" in compact or "tantalum" in compact:
        return "tantalum"

    # 电阻
    if "电阻" in compact or "片式电阻" in compact:
        return "resistor"

    # 存储
    if any(w in compact for w in ["sdram", "ddr", "dram", "内存"]):
        return "dram"
    if any(w in compact for w in ["nand", "flash", "emmc"]):
        return "nand"
    if any(w in compact for w in ["存储芯片", "存储", "memory"]):
        return "dram"

    # MCU
    if "mcu" in compact or "微控制器" in compact or "单片机" in compact:
        return "mcu"
    if "stm32" in compact or "gd32" in compact:
        return "mcu"

    # 功率器件
    if any(w in compact for w in ["igbt", "ipm", "功率模块"]):
        return "power_module"
    if any(w in compact for w in ["mosfet", "mos管", "sic"]):
        return "mosfet"

    # PCB
    if "pcb" in compact or "铜箔" in compact or "覆铜板" in compact or "电路板" in compact or "印制板" in compact or "玻纤布" in compact:
        return "pcb"

    # 电源
    if "电源芯片" in compact or "buck" in compact or "ldo" in compact or "dcdc" in compact or "电源管理" in compact:
        return "power_ic"
    if "电源ic" in compact:
        return "power_ic"

    # 分立器件
    if any(w in compact for w in ["二极管", "三极管", "整流桥", "分立", "二三极管"]):
        return "discrete_passive"

    # 连接器
    if "连接器" in compact or "接插件" in compact:
        return "connector"

    # 晶振
    if "晶振" in compact or "晶体" in compact or "tcxo" in compact or "ocxo" in compact:
        return "crystal"

    # 继电器
    if "继电器" in compact:
        return "relay"

    # 半导体（通用）
    if any(w in compact for w in ["晶圆", "晶圆代工", "fab", "foundry"]):
        return "semiconductor"

    return None


def _extract_mpn(text: str) -> str | None:
    pattern = re.compile(r"\b[A-Z0-9]{2,}[A-Z][A-Z0-9\-]{4,}\b")
    candidates = [m.group(0) for m in pattern.finditer(text.upper())]
    stop_words = {"MLCC", "PRICE", "SHORTAGE", "ALLOCATION"}
    for candidate in candidates:
        if candidate not in stop_words and any(ch.isdigit() for ch in candidate):
            return candidate
    return None


def _extract_series(mpn: str | None) -> str | None:
    if not mpn:
        return None
    match = re.match(r"([A-Z]+\d+)", mpn)
    return match.group(1) if match else None


def _extract_price_increase(text: str) -> tuple[float | None, float | None]:
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*%\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*%", text)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))
    single_match = re.search(r"(?:涨价|上调|increase|adjustment)[^\d]{0,12}(\d+(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    if single_match:
        value = float(single_match.group(1))
        return value, value
    return None, None


def _extract_lead_time(text: str) -> int | None:
    match = re.search(r"(?:交期|货期|lead\s*time)[^\d]{0,12}(?:延长至|至|为)?\s*(\d+)\s*(?:周|weeks|week)", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_effective_date(text: str) -> str | None:
    if "即日起" in text:
        return "即日起"
    match = re.search(r"20\d{2}[年\-/]\d{1,2}[月\-/]\d{1,2}日?", text)
    return match.group(0) if match else None


def _event_type(text: str, increase_max: float | None, lead_time: int | None, shortage: bool) -> str:
    if increase_max is not None or _contains_any(text, PRICE_WORDS):
        return "price_increase"
    if lead_time is not None:
        return "lead_time"
    if shortage:
        return "shortage"
    return "other"


def _score_confidence(source_type: str, brand: str | None, category: str | None, mpn: str | None,
                      increase_max: float | None, lead_time: int | None, shortage: bool, text: str) -> tuple[float, str]:
    score = 0.2
    reasons = []
    if source_type in {"supplier_notice", "email", "website", "manual"}:
        score += 0.2
        reasons.append("来源较可靠")
    if brand:
        score += 0.15
        reasons.append("明确品牌")
    if category:
        score += 0.20
        reasons.append("明确品类")
    if mpn:
        score += 0.15
        reasons.append("明确型号")
    if increase_max is not None:
        score += 0.12
        reasons.append("明确涨价幅度")
    if lead_time is not None:
        score += 0.08
        reasons.append("明确交期")
    if shortage:
        score += 0.08
        reasons.append("明确缺货/紧缺")
    if _contains_any(text, RUMOR_WORDS) or source_type in {"wechat", "wechat_mp"}:
        score -= 0.25
        reasons.append("存在传闻或社交来源降权")
    score = max(0.0, min(round(score, 2), 0.99))
    return score, "；".join(reasons) if reasons else "信息不足"


def _review_status(confidence: float, text: str) -> str:
    if confidence >= 0.8 and not _contains_any(text, RUMOR_WORDS):
        return "auto_confirmed"
    if confidence >= 0.5:
        return "need_review"
    return "observation"


def _contains_any(text: str, words: list[str]) -> bool:
    lowered = text.lower()
    return any(word.lower() in lowered for word in words)
