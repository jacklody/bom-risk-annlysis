"""文档解析服务 (T2-012)。

利用 LLM 从非结构化文档（供应商涨价函、缺货通知、行业报告PDF）中
提取结构化供应链风险事件。

核心流程:
1. 接收文档文本内容和可选的文档类型提示
2. 构造 prompt（system: 事件提取框架 + JSON格式要求; user: 文档文本）
3. 调用 LLM 获取结构化事件列表
4. 解析输出并验证 JSON Schema
5. LLM 调用失败时降级为正则提取

降级策略:
- document_parser 降级为正则提取:
  使用正则表达式从文本中提取涨价幅度、日期、物料名称等关键信息，
  生成低置信度（confidence=0.3）的事件记录，标记为降级输出。

依赖:
    - LLMServiceBase: LLM 服务基类
    - document_parser prompts: Prompt 模板
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional

from app.services.llm.base import LLMCallResult, LLMServiceBase
from app.services.llm.prompts.document_parser import (
    DOCUMENT_PARSER_EVENT_FIELDS,
    DOCUMENT_PARSER_OUTPUT_SCHEMA,
    DOCUMENT_PARSER_REQUIRED_FIELDS,
    DOCUMENT_PARSER_SYSTEM_PROMPT,
    DOCUMENT_PARSER_USER_PROMPT_TEMPLATE,
    DOCUMENT_PARSER_VALID_DOC_TYPES,
    DOCUMENT_PARSER_VALID_EVENT_TYPES,
    DOCUMENT_PARSER_VALID_IMPACT_LEVELS,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 降级: 正则提取
# ═══════════════════════════════════════════════════════════════════════════════

# 涨价幅度正则模式
_PRICE_PATTERNS = [
    # 中文格式: "涨价15%" / "上调 10%" / "涨幅为12.5%"
    re.compile(r"涨[价幅升调]+\s*(?:约|约\s*)?(\d+(?:\.\d+)?)\s*[%％]"),
    re.compile(r"上调\s*(?:价格\s*)?(?:约|约\s*)?(\d+(?:\.\d+)?)\s*[%％]"),
    re.compile(r"涨幅[为达约]?\s*(\d+(?:\.\d+)?)\s*[%％]"),
    re.compile(r"提价\s*(\d+(?:\.\d+)?)\s*[%％]"),
    re.compile(r"价格.*?上涨\s*(\d+(?:\.\d+)?)\s*[%％]"),
    # 英文格式: "increase by 15%" / "price adjustment of 10%"
    re.compile(r"increas\w*\s*(?:by\s*)?(\d+(?:\.\d+)?)\s*%"),
    re.compile(r"price\s+adjustment\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%"),
    re.compile(r"(\d+(?:\.\d+)?)\s*%\s*(?:price\s+)?increas", re.IGNORECASE),
]

# 日期正则模式
_DATE_PATTERNS = [
    # 中文日期: "2024年7月1日" / "2024-07-01" / "2024/7/1"
    re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})"),
    # 季度格式: "2024-Q3" / "2024年第三季度"
    re.compile(r"(\d{4})\s*[-]?\s*Q([1-4])"),
    re.compile(r"(\d{4})\s*年\s*第[一二三四]季度"),
    # 相对日期: "即日起" / "下月起"
    re.compile(r"自\s*(即日起|即日起|即日|下月|下季度)"),
]

# 物料/品类关键词
_MATERIAL_KEYWORDS = [
    "MLCC", "MCU", "MOSFET", "IGBT", "FPGA", "DRAM", "NAND", "Flash",
    "SoC", "PMIC", "LDO", "DC-DC", "ADC", "DAC", "TVS", "ESD",
    "电感", "变压器", "晶振", "振荡器", "连接器", "继电器",
    "电阻", "电容", "二极管", "三极管", "传感器",
    "PCB", "覆铜板", "晶圆", "芯片", "集成电路",
    "陶瓷电容", "铝电解电容", "钽电容", "薄膜电容",
    "微控制器", "存储器", "功率器件", "模拟芯片",
]

# 厂商名称
_MANUFACTURER_KEYWORDS = [
    "村田", "Murata", "TDK", "太阳诱电", "Taiyo Yuden", "国巨", "Yageo",
    "三星电机", "Samsung Electro", "风华高科", "三环集团", "宇阳科技",
    "意法半导体", "ST", "STM", "英飞凌", "Infineon", "德州仪器", "TI",
    "恩智浦", "NXP", "微芯", "Microchip", "瑞萨", "Renesas",
    "台积电", "TSMC", "三星", "Samsung", "中芯国际", "SMIC",
    "兆易创新", "GD", "华大", "雅特力", "AT32",
    "安森美", "ON Semi", " Vishay", "威世",
]

# 文档类型自动识别关键词
_DOC_TYPE_KEYWORDS = {
    "price_increase": [
        "涨价", "调价", "价格调整", "上调", "提价", "涨幅",
        "price increase", "price adjustment", "price hike",
    ],
    "shortage": [
        "缺货", "供应紧张", "交期延长", "产能不足", "配额",
        "shortage", "supply tight", "lead time", "allocation",
    ],
    "report": [
        "报告", "分析", "研究", "展望", "趋势",
        "report", "analysis", "research", "outlook", "trend",
    ],
}


def _extract_price_change(text: str) -> Optional[float]:
    """从文本中提取涨价幅度百分比。"""
    for pattern in _PRICE_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                return float(match.group(1))
            except (ValueError, IndexError):
                continue
    return None


def _extract_date(text: str) -> Optional[str]:
    """从文本中提取日期，返回 YYYY-MM-DD 格式。"""
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            groups = match.groups()
            if len(groups) >= 3:
                try:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])
                    if 2000 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31:
                        return f"{year:04d}-{month:02d}-{day:02d}"
                except (ValueError, IndexError):
                    continue
            elif len(groups) == 2:
                # Q季度格式
                try:
                    year = int(groups[0])
                    quarter = int(groups[1])
                    month = (quarter - 1) * 3 + 1
                    if 2000 <= year <= 2099:
                        return f"{year:04d}-{month:02d}-01"
                except (ValueError, IndexError):
                    continue
    return None


def _extract_materials(text: str) -> list[str]:
    """从文本中提取物料/品类名称。"""
    found = []
    text_upper = text.upper()
    for kw in _MATERIAL_KEYWORDS:
        if kw.upper() in text_upper:
            found.append(kw)
    return found[:10]  # 最多返回10个


def _extract_manufacturers(text: str) -> list[str]:
    """从文本中提取厂商名称。"""
    found = []
    text_upper = text.upper()
    for kw in _MANUFACTURER_KEYWORDS:
        if kw.upper() in text_upper:
            found.append(kw)
    return found[:10]


def _detect_doc_type(text: str) -> str:
    """自动识别文档类型。"""
    text_lower = text.lower()
    scores = {}
    for doc_type, keywords in _DOC_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text_lower)
        scores[doc_type] = score
    best_type = max(scores, key=scores.get)
    return best_type if scores[best_type] > 0 else "other"


def _regex_fallback_parse(text_content: str, doc_type: str) -> dict[str, Any]:
    """正则降级提取逻辑。

    从文本中用正则表达式提取关键信息，生成低置信度事件。

    Args:
        text_content: 文档文本内容
        doc_type: 文档类型提示

    Returns:
        符合输出 schema 的降级字典
    """
    events = []

    # 提取涨价幅度
    price_pct = _extract_price_change(text_content)
    # 提取日期
    effective_date = _extract_date(text_content)
    # 提取物料
    materials = _extract_materials(text_content)
    # 提取厂商
    manufacturers = _extract_manufacturers(text_content)
    # 识别文档类型
    classified_type = _detect_doc_type(text_content) if doc_type == "auto" else doc_type

    # 根据提取结果构造事件
    if price_pct is not None:
        # 提取一个证据段落（包含涨价关键词的前后文）
        evidence = _extract_evidence_text(text_content, ["涨价", "调价", "上调", "涨幅", "price"])

        impact_level = "low"
        if price_pct >= 10:
            impact_level = "high"
        elif price_pct >= 3:
            impact_level = "medium"

        title = f"物料涨价 {price_pct}%"
        if materials:
            title = f"{'、'.join(materials[:3])} 涨价 {price_pct}%"

        events.append({
            "event_type": "price_increase",
            "title": title,
            "description": f"文档提及涨价幅度为 {price_pct}%，"
                           f"涉及品类：{'、'.join(materials) if materials else '未明确'}，"
                           f"涉及厂商：{'、'.join(manufacturers) if manufacturers else '未明确'}",
            "affected_categories": materials if materials else ["未明确"],
            "affected_manufacturers": manufacturers if manufacturers else ["未明确"],
            "effective_date": effective_date,
            "impact_level": impact_level,
            "price_change_pct": price_pct,
            "confidence": 0.3,
            "evidence_text": evidence,
        })

    # 检查是否包含缺货相关信息
    shortage_keywords = ["缺货", "供应紧张", "交期延长", "产能不足", "shortage", "lead time"]
    has_shortage = any(kw in text_content.lower() for kw in shortage_keywords)
    if has_shortage and price_pct is None:
        evidence = _extract_evidence_text(text_content, shortage_keywords)
        events.append({
            "event_type": "shortage",
            "title": "供应链缺货/交期延长",
            "description": f"文档提及缺货或交期延长相关信息，"
                           f"涉及品类：{'、'.join(materials) if materials else '未明确'}",
            "affected_categories": materials if materials else ["未明确"],
            "affected_manufacturers": manufacturers if manufacturers else ["未明确"],
            "effective_date": effective_date,
            "impact_level": "medium",
            "price_change_pct": None,
            "confidence": 0.3,
            "evidence_text": evidence,
        })

    # 文档摘要（取前200字）
    summary = text_content[:200].strip()
    if len(text_content) > 200:
        summary += "..."

    return {
        "events": events,
        "doc_summary": summary,
        "doc_type_classified": classified_type if classified_type in DOCUMENT_PARSER_VALID_DOC_TYPES else "other",
        "_degraded": True,
        "_degrade_method": "regex",
    }


def _extract_evidence_text(text: str, keywords: list[str]) -> str:
    """从文本中提取包含关键词的证据段落。

    返回关键词所在句子（以句号/换行符为界），最多300字。
    """
    # 按句子切分
    sentences = re.split(r"[。\n;；]", text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for kw in keywords:
            if kw in sentence.lower():
                return sentence[:300]
    # 未找到匹配句子，返回文本前100字
    return text[:100].strip()


def _validate_event_structure(event: dict) -> bool:
    """验证单个事件的结构完整性。"""
    if not isinstance(event, dict):
        return False
    for field in DOCUMENT_PARSER_EVENT_FIELDS:
        if field not in event:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# 主服务类
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentParser(LLMServiceBase):
    """从非结构化文档中提取供应链风险事件 (T2-012)。

    利用 LLM 对文档文本进行语义理解，提取结构化的风险事件信息，
    包括事件类型、影响品类/厂商、生效日期、影响等级等。

    Usage::

        from app.services.llm.document_parser import DocumentParser

        parser = DocumentParser()
        result = parser.parse(
            text_content="关于MLCC产品调价通知...",
            doc_type="price_increase",
        )
        # result.data 包含:
        # {
        #   "events": [...],
        #   "doc_summary": "...",
        #   "doc_type_classified": "price_increase"
        # }
    """

    SERVICE_NAME = "DocumentParser"
    DEFAULT_MAX_TOKENS = 3000  # 文档较长

    # ────────────────────────────────────────────────────────
    # 子类实现: Prompt 构造
    # ────────────────────────────────────────────────────────

    def _build_system_prompt(self) -> str:
        """返回文档解析的 system prompt。

        强制要求 JSON 格式输出，包含事件提取框架和输出 schema。
        """
        return DOCUMENT_PARSER_SYSTEM_PROMPT

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        """根据文档内容构造 user prompt。

        Args:
            context: 包含 text_content 和 doc_type 的字典

        Returns:
            格式化的 user prompt 字符串
        """
        doc_type = context.get("doc_type", "auto")
        if doc_type == "auto":
            doc_type_hint = "自动识别（请根据内容判断文档类型）"
        else:
            doc_type_hint = f"已知文档类型：{doc_type}"

        # 截取文档内容（控制 token 消耗）
        text_content = context.get("text_content", "")
        max_chars = 6000  # 约 3000 中文字 ≈ 4000 tokens
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n\n[文档内容已截断...]"

        return DOCUMENT_PARSER_USER_PROMPT_TEMPLATE.format(
            doc_type_hint=doc_type_hint,
            doc_content=text_content,
        )

    # ────────────────────────────────────────────────────────
    # 子类实现: 输出验证
    # ────────────────────────────────────────────────────────

    def _validate_output(self, data: dict) -> bool:
        """验证 LLM 输出的 JSON 包含所有必要字段且格式正确。

        必要字段:
        - events: 事件列表（可为空数组）
        - doc_summary: 文档摘要（非空字符串）
        - doc_type_classified: 文档类型分类

        每个事件必须包含必要字段。

        Args:
            data: LLM 返回并解析后的字典

        Returns:
            是否通过验证
        """
        if not isinstance(data, dict):
            return False

        # 检查顶层必要字段
        for field_name in DOCUMENT_PARSER_REQUIRED_FIELDS:
            if field_name not in data:
                logger.warning(
                    "[DocumentParser] 输出缺少必要字段: %s", field_name
                )
                return False

        # 检查 events 是列表
        events = data.get("events")
        if not isinstance(events, list):
            logger.warning("[DocumentParser] events 字段不是列表")
            return False

        # 检查每个事件结构
        for i, event in enumerate(events):
            if not _validate_event_structure(event):
                logger.warning(
                    "[DocumentParser] 第 %d 个事件结构不完整", i
                )
                return False

            # 验证枚举值
            event_type = event.get("event_type", "")
            if event_type not in DOCUMENT_PARSER_VALID_EVENT_TYPES:
                logger.warning(
                    "[DocumentParser] 无效的事件类型: %s", event_type
                )
                return False

            impact_level = event.get("impact_level", "")
            if impact_level not in DOCUMENT_PARSER_VALID_IMPACT_LEVELS:
                logger.warning(
                    "[DocumentParser] 无效的影响等级: %s", impact_level
                )
                return False

        # 检查 doc_type_classified 值
        doc_type = data.get("doc_type_classified", "")
        if doc_type not in DOCUMENT_PARSER_VALID_DOC_TYPES:
            logger.warning(
                "[DocumentParser] 无效的文档类型分类: %s", doc_type
            )
            return False

        # 检查 doc_summary 非空
        summary = data.get("doc_summary", "")
        if not summary or not str(summary).strip():
            logger.warning("[DocumentParser] doc_summary 为空")
            return False

        return True

    # ────────────────────────────────────────────────────────
    # 子类实现: 降级逻辑
    # ────────────────────────────────────────────────────────

    def _fallback(self, context: dict[str, Any]) -> dict:
        """降级输出：LLM 调用失败时使用正则提取关键信息。

        通过正则表达式从文档文本中提取涨价幅度、日期、物料名称等
        关键信息，生成 confidence=0.3 的低置信度事件。

        Args:
            context: 原始上下文数据

        Returns:
            降级结果字典
        """
        text_content = context.get("text_content", "")
        doc_type = context.get("doc_type", "auto")
        return _regex_fallback_parse(text_content, doc_type)

    # ────────────────────────────────────────────────────────
    # 公开接口
    # ────────────────────────────────────────────────────────

    def parse(self, text_content: str, doc_type: str = "auto") -> LLMCallResult:
        """解析文档内容，提取结构化事件。

        主调用入口。构造 context 字典后调用基类的 run() 方法，
        基类负责完整的 调用→解析→降级 流程。

        Args:
            text_content: 文档文本内容
            doc_type: 文档类型(auto/price_increase/shortage/report)

        Returns:
            LLMCallResult: 包含结构化事件列表的结果
        """
        context = {
            "text_content": text_content,
            "doc_type": doc_type,
        }
        return self.run(context)
