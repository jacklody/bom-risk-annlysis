"""关注指令智能体"""

import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.watch import WatchCommand
from app.models.event import MarketEvent, EventType, Severity
from app.models.bom import BomItem, BomProject
from app.services.llm_client import LLMClient
from app.knowledge.brand_category_map import ALIAS_TO_BRAND, normalize_brand
from app.services.incremental_scanner import IncrementalScanner


class IntelAgent:

    def __init__(self, db: Session):
        self.db = db
        self.llm = LLMClient()

    def execute(self, raw_input: str) -> WatchCommand:
        cmd = WatchCommand(raw_input=raw_input, status="researching")
        self.db.add(cmd)
        self.db.commit()
        self.db.refresh(cmd)

        try:
            parsed = self._parse_intent(raw_input)
            research = self._research(parsed, raw_input)
            affected = self._match_against_boms(parsed)
            analysis = self._analyze(raw_input, parsed, research, affected)
            event_ids = self._generate_events(parsed, research)

            if event_ids:
                scanner = IncrementalScanner(self.db)
                scanner.scan_all_projects()

            cmd.parsed_brand = parsed.get("brand")
            cmd.parsed_category = parsed.get("category")
            cmd.parsed_keywords = json.dumps(parsed.get("keywords", []))
            cmd.research_summary = analysis.get("summary", "")
            cmd.research_detail = json.dumps(research, ensure_ascii=False)
            cmd.generated_event_ids = ",".join(str(eid) for eid in event_ids)
            cmd.affected_project_count = len(affected)
            cmd.suggestion = analysis.get("suggestion", "")
            cmd.status = "done"
            cmd.resolved_at = datetime.now(timezone.utc)
            self.db.commit()
        except Exception as e:
            cmd.status = "failed"
            cmd.research_summary = str(e)
            self.db.commit()

        return cmd

    def _parse_intent(self, raw_input: str) -> dict:
        if self.llm.available:
            return self._llm_parse(raw_input)
        return self._keyword_parse(raw_input)

    def _llm_parse(self, raw_input: str) -> dict:
        prompt = f"""分析以下采购人员输入的关注指令，提取结构化信息：

指令: {raw_input}

返回JSON：
{{"brand": "品牌标准名，不确定填null", "category": "品类，不确定填null",
  "keywords": ["型号或关键词列表"], "model_anchor": "型号锚点，不确定填null",
  "concern": "交期/价格/供应/全部", "is_specific_model": true/false}}"""

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.llm.api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return self._keyword_parse(raw_input)

    def _keyword_parse(self, raw_input: str) -> dict:
        lower = raw_input.lower()
        result = {
            "brand": None, "category": None, "keywords": [raw_input],
            "model_anchor": None, "concern": "all", "is_specific_model": False,
        }
        for alias, std_name in ALIAS_TO_BRAND.items():
            if len(alias) >= 3 and alias.lower() in lower:
                result["brand"] = std_name
                break
        return result

    def _research(self, parsed: dict, raw_input: str) -> dict:
        return {
            "method": "llm_extraction",
            "parsed": parsed,
        }

    def _match_against_boms(self, parsed: dict) -> list:
        affected = []
        brand = parsed.get("brand")
        keywords = parsed.get("keywords", [])
        if not brand and not keywords:
            return affected

        projects = self.db.query(BomProject).filter(
            BomProject.status == "active"
        ).all()

        for project in projects:
            items = self.db.query(BomItem).filter(
                BomItem.bom_upload_id == project.id
            ).all()
            for item in items:
                matched = False
                if brand and item.normalized_brand:
                    nb = normalize_brand(item.normalized_brand)
                    if nb and nb == brand:
                        matched = True
                if not matched:
                    for kw in keywords:
                        if item.raw_part_number and kw.lower() in item.raw_part_number.lower():
                            matched = True
                            break
                if matched:
                    affected.append({
                        "project_id": project.id,
                        "project_name": project.project_name or project.filename,
                        "item_id": item.id,
                        "part_number": item.raw_part_number,
                    })
        return affected

    def _analyze(self, raw_input, parsed, research, affected) -> dict:
        if self.llm.available:
            return self._llm_analyze(raw_input, parsed, affected)
        return {
            "summary": f"已记录关注指令，影响 {len(affected)} 个BOM项目",
            "suggestion": "建议手动确认交期/库存现状",
        }

    def _llm_analyze(self, raw_input, parsed, affected) -> dict:
        prompt = f"""作为电子元器件供应链分析师，请综合分析：

原始指令: {raw_input}
解析结果: {json.dumps(parsed, ensure_ascii=False)}
影响BOM项目数: {len(affected)}

返回JSON：{{"summary": "结论(2-3句话)", "suggestion": "建议行动(1-2句话)"}}"""

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.llm.api_key)
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=400,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return {"summary": "调研完成", "suggestion": "建议确认"}

    def _generate_events(self, parsed: dict, research: dict) -> list[int]:
        event_ids = []
        brand = parsed.get("brand")
        category = parsed.get("category")
        if brand:
            evt = MarketEvent(
                brand=brand,
                category=category,
                event_type=EventType.OTHER,
                severity=Severity.MEDIUM,
                confidence=0.7,
                source_name="manual_watch",
                raw_text=json.dumps(parsed, ensure_ascii=False),
                cross_validated=0,
            )
            self.db.add(evt)
            self.db.commit()
            event_ids.append(evt.id)
        return event_ids
