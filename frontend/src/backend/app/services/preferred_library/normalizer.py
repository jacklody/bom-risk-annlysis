import re

BRAND_ALIASES = {
    "国巨": "YAGEO",
    "村田": "MURATA",
    "三星": "SAMSUNG",
    "风华": "FH",
    "华新科": "WALSIN",
}


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_brand(value: object) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if "/" in text:
        parts = [p.strip() for p in text.split("/") if p.strip()]
        for part in parts:
            upper = part.upper()
            if re.search(r"[A-Z]", upper):
                return BRAND_ALIASES.get(part, upper)
        text = parts[0] if parts else text
    return BRAND_ALIASES.get(text, text.upper())


def normalize_mpn(value: object) -> str:
    text = normalize_text(value).upper()
    return re.sub(r"[^A-Z0-9]", "", text)


def parse_preferred_level(status_text: str) -> tuple[str, str]:
    text = normalize_text(status_text)
    if "禁用" in text or "禁选" in text:
        return "unknown", "blocked"
    if "限用" in text or "限选" in text:
        return "unknown", "restricted"
    if "待评审" in text or "待确认" in text:
        return "unknown", "pending_review"
    if "强推" in text or "跨3" in text or "跨 3" in text:
        return "strong_recommended", "preferred"
    if "中推" in text or "跨2" in text or "跨 2" in text:
        return "medium_recommended", "preferred"
    if "通用" in text or "推荐" in text:
        return "recommended", "preferred"
    if text:
        return "normal", "general"
    return "unknown", "unknown"
