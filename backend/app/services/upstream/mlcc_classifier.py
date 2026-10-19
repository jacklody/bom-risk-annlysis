from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class MlccClassificationResult:
    raw_text: str
    is_mlcc: bool
    high_capacitance_flag: bool
    capacitance: str | None = None
    capacitance_uf: float | None = None
    voltage: str | None = None
    dielectric: str | None = None
    package_size: str | None = None
    category: str = "unknown"
    confidence: float = 0.0
    reason: str = ""


_NON_MLCC_TERMS = (
    "aluminum",
    "electrolytic",
    "铝电解",
    "电解",
    "tantalum",
    "钽",
    "film",
    "薄膜",
    "polymer",
    "聚合物",
    "supercap",
)

_DIELECTRIC_PATTERN = re.compile(r"\b(C0G|NP0|X5R|X6S|X7R|X7S|Y5V|Z5U)\b", re.IGNORECASE)
_CAP_PATTERN = re.compile(r"(?<![A-Z0-9.])(\d+(?:\.\d+)?)\s*(PF|NF|UF|ΜF|μF|uF)(?![A-Z])", re.IGNORECASE)
_VOLTAGE_PATTERN = re.compile(r"(?<![A-Z0-9.])(\d+(?:\.\d+)?)\s*V(?![A-Z])", re.IGNORECASE)
_PACKAGE_PATTERN = re.compile(r"\b(0201|0402|0603|0805|1206|1210|1812|2220|2225)\b", re.IGNORECASE)


def _normalize_capacitance(value: str, unit: str) -> tuple[str, float]:
    unit_upper = unit.upper().replace("Μ", "U").replace("μ", "U")
    number = float(value)
    if unit_upper == "PF":
        uf = number / 1_000_000
        suffix = "pF"
    elif unit_upper == "NF":
        uf = number / 1000
        suffix = "nF"
    else:
        uf = number
        suffix = "uF"

    normalized_number = int(number) if number.is_integer() else number
    return f"{normalized_number}{suffix}", uf


def classify_mlcc(text: str | None) -> MlccClassificationResult:
    """Classify whether a part description looks like ordinary/high-cap MLCC.

    MVP rule: high-capacitance MLCC is treated as >= 10uF ceramic capacitor.
    This intentionally avoids marking aluminum electrolytic, tantalum, and film
    capacitors as MLCC even if they contain large capacitance values.
    """
    raw_text = text or ""
    normalized = raw_text.strip()
    lowered = normalized.lower()

    if not normalized:
        return MlccClassificationResult(raw_text=raw_text, is_mlcc=False, high_capacitance_flag=False)

    if any(term in lowered for term in _NON_MLCC_TERMS):
        return MlccClassificationResult(
            raw_text=raw_text,
            is_mlcc=False,
            high_capacitance_flag=False,
            category="not_mlcc",
            confidence=0.9,
            reason="description contains non-MLCC capacitor family terms",
        )

    cap_match = _CAP_PATTERN.search(normalized)
    dielectric_match = _DIELECTRIC_PATTERN.search(normalized)
    voltage_match = _VOLTAGE_PATTERN.search(normalized)
    package_match = _PACKAGE_PATTERN.search(normalized)

    capacitance = None
    capacitance_uf = None
    if cap_match:
        capacitance, capacitance_uf = _normalize_capacitance(cap_match.group(1), cap_match.group(2))

    dielectric = dielectric_match.group(1).upper().replace("NP0", "C0G") if dielectric_match else None
    voltage = None
    if voltage_match:
        voltage_value = float(voltage_match.group(1))
        voltage_number = int(voltage_value) if voltage_value.is_integer() else voltage_value
        voltage = f"{voltage_number}V"
    package_size = package_match.group(1) if package_match else None

    explicit_mlcc = "mlcc" in lowered or "陶瓷" in lowered or "瓷介" in lowered
    looks_like_mlcc = bool(capacitance and dielectric and package_size) or bool(explicit_mlcc and capacitance)

    if not looks_like_mlcc:
        return MlccClassificationResult(
            raw_text=raw_text,
            is_mlcc=False,
            high_capacitance_flag=False,
            capacitance=capacitance,
            capacitance_uf=capacitance_uf,
            voltage=voltage,
            dielectric=dielectric,
            package_size=package_size,
            category="unknown",
            confidence=0.35,
            reason="not enough ceramic capacitor evidence",
        )

    high_cap = bool(capacitance_uf is not None and capacitance_uf >= 10.0)
    category = "high_cap_mlcc" if high_cap else "mlcc"
    confidence = 0.95 if dielectric and package_size else 0.75
    reason = "capacitance >= 10uF" if high_cap else "ordinary MLCC capacitance"

    return MlccClassificationResult(
        raw_text=raw_text,
        is_mlcc=True,
        high_capacitance_flag=high_cap,
        capacitance=capacitance,
        capacitance_uf=capacitance_uf,
        voltage=voltage,
        dielectric=dielectric,
        package_size=package_size,
        category=category,
        confidence=confidence,
        reason=reason,
    )
