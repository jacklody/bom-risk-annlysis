"""
LLM 客户端 — v4.0 改造版
支持 DeepSeek（默认）及任何 OpenAI 兼容 API。
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    LLM 客户端封装。
    使用 OpenAI SDK 兼容模式调用 DeepSeek / 其他兼容 API。
    """

    def __init__(self):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.timeout = settings.llm_timeout
        self.max_tokens = settings.llm_max_tokens
        self._client = None

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        """延迟初始化 OpenAI 客户端"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                    timeout=self.timeout,
                )
            except ImportError:
                logger.error("openai 库未安装，请执行: pip install openai")
                return None
        return self._client

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = None) -> Optional[str]:
        """通用 LLM 调用，返回文本响应"""
        if not self.available:
            logger.warning("LLM API key 未配置")
            return None

        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return None

    def _extract_json(self, text: str) -> Optional[dict]:
        """从 LLM 响应文本中提取 JSON 对象"""
        if not text:
            return None
        # 尝试找 { ... } 块
        json_start = text.find("{")
        json_end = text.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(text[json_start:json_end])
            except json.JSONDecodeError:
                # 尝试修复常见问题
                snippet = text[json_start:json_end]
                snippet = snippet.replace("'", '"')  # 单引号→双引号
                try:
                    return json.loads(snippet)
                except json.JSONDecodeError:
                    logger.warning(f"LLM 返回的 JSON 无法解析: {snippet[:200]}")
                    return None
        return None

    # ================================================================
    # 功能 1: 市场事件抽取（保留原有功能，改用 OpenAI 兼容格式）
    # ================================================================
    def extract_event(self, text: str, title: str = "") -> dict:
        """从新闻/报告文本中提取市场事件结构化信息"""
        if not self.available:
            return {"error": "LLM API key not configured", "confidence": 0.0}

        system_prompt = "你是专业的电子元器件供应链分析师，擅长从行业报告中提取结构化的市场事件信息。"

        user_prompt = f"""请从以下文本中提取市场事件信息，严格按JSON格式输出：

{{
  "brand": "受影响品牌标准名称（如 村田/Murata、意法半导体/ST），无则null",
  "category": "受影响品类（如 MLCC高容、MCU/微控制器），无则null",
  "event_type": "shortage/price_increase/capacity_issue/eol/policy/disaster/other",
  "severity": "critical/high/medium/low/unknown",
  "estimated_lead_time_impact_weeks": "预估交期延长周数（整数），无法判断填null",
  "estimated_price_impact_pct": "预估价格涨幅百分比（浮点数），无法判断填null",
  "duration_start": "影响开始时间（ISO格式），无则null",
  "duration_end": "影响结束时间（ISO格式），无则null",
  "confidence": "信心度(0.0-1.0)",
  "reasoning": "简要推理过程（1-2句话）"
}}

规则：
- 只提取文本中明确提到的信息，不要推断或泛化
- "MLCC涨价"不能泛化为"所有电容器涨价"
- "ST MCU缺货"只影响ST品牌MCU，不影响其他品牌
- 信息不足时对应字段填null
- 纯行情概述无具体事件时 event_type=other, severity=low

标题: {title}
正文: {text[:2000]}"""

        result = self._call(system_prompt, user_prompt, max_tokens=1000)
        parsed = self._extract_json(result)
        if parsed:
            return parsed
        return {"error": "Failed to extract JSON from LLM response", "confidence": 0.0, "raw": result}

    # ================================================================
    # 功能 2: 品类分类 LLM 兜底（v4.0 新增）
    # ================================================================
    def classify_component(self, description: str, manufacturer: str = "") -> dict:
        """
        LLM 品类分类兜底。
        当规则匹配失败时调用，返回品类分类结果。
        返回格式与 ComponentCategoryResult 对齐。
        """
        if not self.available:
            return {"category": "unknown", "confidence": 0.0, "error": "LLM not available"}

        system_prompt = "你是电子元器件品类分类专家。根据物料描述和制造商信息，将物料分类到预定义的品类中。"

        user_prompt = f"""请将以下电子元器件分类到最匹配的品类。

物料描述: {description}
制造商: {manufacturer or "未知"}

可选品类列表（选择最匹配的一个）：
- mlcc: MLCC/片式多层陶瓷电容（含高容MLCC）
- resistor: 贴片电阻/厚膜电阻/薄膜电阻/采样电阻
- inductor_transformer: 电感/变压器/磁珠
- aluminum_electrolytic_capacitor: 铝电解电容
- film_capacitor: 薄膜电容/安规电容
- tantalum_capacitor: 钽电容
- mcu: MCU/微控制器/单片机（STM32/GD32等）
- power_ic: 电源芯片/PMIC/DC-DC/LDO
- mosfet: MOSFET/IGBT/SiC/GaN功率器件
- discrete_diode: 二极管/三极管/TVS/ESD/整流
- analog_ic: 模拟芯片/运放/ADC/DAC
- memory: 存储芯片/DRAM/NAND/Flash
- fpga_cpld: FPGA/CPLD
- relay: 继电器
- connector: 连接器/端子/排针/USB
- wire_harness: 线束/电缆
- switch: 开关/按键
- crystal_oscillator: 晶振/振荡器
- sensor: 传感器/霍尔/温度传感器
- varistor_thermistor: 压敏电阻/热敏电阻
- pcb: PCB/线路板/覆铜板
- power_module: 功率模块/IPM
- other: 无法归入以上品类

请严格按以下JSON格式输出：
{{
  "category": "品类标识（从上面列表选）",
  "confidence": 0.0到1.0的信心度,
  "is_high_risk": true/false（是否是偏门/小众规格，供应商少、容易被挤占产能的物料）,
  "risk_reason": "判断为高风险的原因（如 特殊封装/高功率/高容值/供应商仅2-3家等），非高风险则null"
}}

注意：
- 只根据描述信息判断，不要猜测
- is_high_risk 重点关注：非标封装（如0805但500mW高功率）、高容MLCC（如X7R/50V/1uF）、冷门品牌、特殊参数
- 信心度低于0.5时 category 填 "unknown"
"""

        result = self._call(system_prompt, user_prompt, max_tokens=500)
        parsed = self._extract_json(result)
        if parsed and "category" in parsed:
            return parsed
        return {"category": "unknown", "confidence": 0.0, "error": "LLM classification failed"}

    def classify_component_batch(self, items: list[dict]) -> list[dict]:
        """
        批量品类分类（一次调用分类多个物料，节省 token）。
        items: [{"description": "...", "manufacturer": "..."}, ...]
        返回: [{"category": "...", "confidence": 0.x, ...}, ...]
        """
        if not self.available or not items:
            return [{"category": "unknown", "confidence": 0.0} for _ in items]

        # 单次最多处理 20 个物料
        batch = items[:20]
        item_list = "\n".join([
            f"{i+1}. 描述:{it.get('description','')} 制造商:{it.get('manufacturer','')}"
            for i, it in enumerate(batch)
        ])

        system_prompt = "你是电子元器件品类分类专家，需要批量分类物料。"

        user_prompt = f"""请对以下 {len(batch)} 个电子元器件逐一分类。

物料列表：
{item_list}

可选品类：mlcc, resistor, inductor_transformer, aluminum_electrolytic_capacitor, film_capacitor, tantalum_capacitor, mcu, power_ic, mosfet, discrete_diode, analog_ic, memory, fpga_cpld, relay, connector, wire_harness, switch, crystal_oscillator, sensor, varistor_thermistor, pcb, power_module, other

请按JSON数组格式输出，每个元素对应一个物料：
[
  {{"index": 1, "category": "品类标识", "confidence": 0.0到1.0, "is_high_risk": true/false, "risk_reason": "原因或null"}},
  ...
]

注意：is_high_risk 关注偏门规格（特殊封装/高功率/高容值/供应商少的冷门物料）"""

        result = self._call(system_prompt, user_prompt, max_tokens=1500)
        if not result:
            return [{"category": "unknown", "confidence": 0.0} for _ in items]

        # 尝试解析 JSON 数组
        try:
            text = result.strip()
            arr_start = text.find("[")
            arr_end = text.rfind("]") + 1
            if arr_start >= 0 and arr_end > arr_start:
                parsed_list = json.loads(text[arr_start:arr_end])
                # 对齐结果
                results = []
                parsed_by_index = {item.get("index", i+1): item for i, item in enumerate(parsed_list)}
                for i in range(len(batch)):
                    r = parsed_by_index.get(i+1, {})
                    results.append({
                        "category": r.get("category", "unknown"),
                        "confidence": r.get("confidence", 0.0),
                        "is_high_risk": r.get("is_high_risk", False),
                        "risk_reason": r.get("risk_reason"),
                    })
                return results
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"批量分类 JSON 解析失败: {e}")

        return [{"category": "unknown", "confidence": 0.0} for _ in items]
