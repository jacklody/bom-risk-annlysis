import json
from sqlalchemy.orm import Session
from app.models.bom import BomItem, BomProject
from app.models.preferred import BomSelectionReview, PreferredPart
from app.services.preferred_library.history_indexer import HistoricalPartIndexer
from app.services.preferred_library.normalizer import normalize_brand, normalize_mpn


class PreferredLibraryReviewService:
    def __init__(self, db: Session):
        self.db = db
        self.history = HistoricalPartIndexer(db)

    def review_project(self, project_id: int) -> dict:
        project = self.db.query(BomProject).filter(BomProject.id == project_id).first()
        if not project:
            return {"error": "Project not found"}
        self.db.query(BomSelectionReview).filter(BomSelectionReview.bom_project_id == project_id).delete()
        items = self.db.query(BomItem).filter(BomItem.bom_upload_id == project_id).order_by(BomItem.row_number).all()
        reviews = []
        for item in items:
            review = self._review_item(project_id, item)
            self.db.add(review)
            reviews.append(review)
        self.db.commit()
        return self._build_response(project, reviews)

    def get_latest_review(self, project_id: int) -> dict:
        project = self.db.query(BomProject).filter(BomProject.id == project_id).first()
        if not project:
            return {"error": "Project not found"}
        reviews = self.db.query(BomSelectionReview).filter(BomSelectionReview.bom_project_id == project_id).order_by(BomSelectionReview.id).all()
        return self._build_response(project, reviews)

    def _review_item(self, project_id: int, item: BomItem) -> BomSelectionReview:
        match = self._match_preferred(item)
        usage = self.history.get_usage(item)
        alternatives = self._find_alternatives(item, exclude_id=match["preferred_part"].id if match["preferred_part"] else None)
        delivery_status, delivery_reason = self._delivery_control(item)
        is_new = usage["usage_count"] == 0
        risk, reason, action = self._selection_decision(match, is_new, delivery_status, alternatives)
        return BomSelectionReview(
            bom_project_id=project_id,
            bom_item_id=item.id,
            preferred_part_id=match["preferred_part"].id if match["preferred_part"] else None,
            match_status=match["status"],
            match_score=match["score"],
            preferred_level=match["preferred_part"].preferred_level if match["preferred_part"] else "unknown",
            control_status=match["preferred_part"].control_status if match["preferred_part"] else "unknown",
            is_new_part=1 if is_new else 0,
            history_usage_count=usage["usage_count"],
            history_project_count=usage["project_count"],
            delivery_control_status=delivery_status,
            delivery_control_reason=delivery_reason,
            selection_risk_level=risk,
            selection_reason=reason,
            selection_action=action,
            recommended_alternatives_json=json.dumps([p.to_dict() for p in alternatives[:5]], ensure_ascii=False),
        )

    def _match_preferred(self, item: BomItem) -> dict:
        part_number = (item.raw_part_number or "").strip()
        brand = normalize_brand(item.raw_brand or item.normalized_brand)
        mpn = normalize_mpn(item.raw_part_number or item.raw_spec)
        if part_number:
            part = self.db.query(PreferredPart).filter(PreferredPart.part_number == part_number).first()
            if part:
                return {"status": "exact_part_number", "score": 1.0, "preferred_part": part}
        if brand and mpn:
            parts = self.db.query(PreferredPart).filter(PreferredPart.normalized_brand == brand, PreferredPart.normalized_mpn == mpn).all()
            if parts:
                return {"status": "exact_brand_mpn", "score": 0.95, "preferred_part": parts[0]}
        if mpn:
            part = self.db.query(PreferredPart).filter(PreferredPart.normalized_mpn == mpn).first()
            if part:
                return {"status": "exact_mpn_package", "score": 0.85, "preferred_part": part}
        return {"status": "not_found", "score": 0.0, "preferred_part": None}

    def _find_alternatives(self, item: BomItem, exclude_id: int | None = None) -> list[PreferredPart]:
        category = (item.raw_category or item.normalized_category or "").strip()
        if not category:
            return []
        query = self.db.query(PreferredPart).filter(PreferredPart.category_level_3.contains(category[:4]))
        if exclude_id:
            query = query.filter(PreferredPart.id != exclude_id)
        return query.order_by(PreferredPart.preferred_level.asc()).limit(5).all()

    def _delivery_control(self, item: BomItem) -> tuple[str, str]:
        risk_level = item.risk_level.value if item.risk_level else "gray"
        reason = " ".join(str(v or "") for v in [item.risk_reason, item.supply_risk_reason, item.supply_risk_tags])
        weeks = item.lead_time_risk_weeks or 0
        confirmed = any(word in reason.lower() for word in ["confirmed", "已确认", "缺货", "shortage", "allocation"])
        if risk_level == "red" and (confirmed or weeks >= 12):
            detail = f"已确认缺货且交期 {weeks} 周，临时禁选。" if weeks else "红色交期风险且证据可信，临时禁选。"
            return "temporary_blocked", detail
        if risk_level == "yellow" or weeks >= 8:
            return "restricted", "存在中等交期风险，需补充供应确认或替代方案。"
        if any(word in reason for word in ["传闻", "可能", "关注"]):
            return "watch", "低置信度行情或交期传闻，仅观察。"
        return "normal", ""

    def _selection_decision(self, match: dict, is_new: bool, delivery_status: str, alternatives: list[PreferredPart]) -> tuple[str, str, str]:
        part = match["preferred_part"]
        if delivery_status == "temporary_blocked":
            return "red", "交期风险联动为临时禁选。", "需研发说明不可替代理由，并由采购/工程确认。"
        if part and part.control_status == "blocked":
            return "red", "命中禁用料。", "禁止选用，需替换为优选物料。"
        if is_new and not part:
            return "red", "不在优选库且历史 BOM 从未出现。", "优先替换为优选库物料；如必须使用需提交选型说明。"
        if delivery_status == "restricted":
            return "yellow", "交期风险联动为限选。", "补充供应确认、库存确认或替代方案。"
        if part and part.control_status in {"pending_review", "restricted"}:
            return "yellow", "命中待评审或限用状态。", "进入待确认清单。"
        if not part:
            return "yellow", "未命中优选库。", "建议从推荐替代料中选择。"
        return "green", "命中优选库。", "可优先使用。"

    def _build_response(self, project: BomProject, reviews: list[BomSelectionReview]) -> dict:
        bom_items_map = {}
        if reviews:
            item_ids = [r.bom_item_id for r in reviews]
            bom_items_list = self.db.query(BomItem).filter(BomItem.id.in_(item_ids)).all()
            bom_items_map = {bi.id: bi for bi in bom_items_list}

        preferred_map = {}
        pref_ids = [r.preferred_part_id for r in reviews if r.preferred_part_id]
        if pref_ids:
            pref_list = self.db.query(PreferredPart).filter(PreferredPart.id.in_(pref_ids)).all()
            preferred_map = {pp.id: pp for pp in pref_list}

        items = []
        for review in reviews:
            data = review.to_dict()
            data["recommended_alternatives"] = json.loads(review.recommended_alternatives_json or "[]")

            # BOM 实际物料明细
            bom_item = bom_items_map.get(review.bom_item_id)
            if bom_item:
                data["bom_part_number"] = bom_item.raw_part_number or ""
                data["bom_brand"] = bom_item.raw_brand or ""
                data["bom_category"] = bom_item.raw_category or ""
                data["bom_total_stock"] = bom_item.total_stock or 0
                data["bom_lead_time_days"] = bom_item.lead_time_days
                data["bom_unit_price"] = bom_item.unit_price
                data["bom_lifecycle_status"] = bom_item.lifecycle_status or "Unknown"
                data["bom_risk_level"] = bom_item.risk_level.value if bom_item.risk_level else "gray"

            # 优选库匹配物料明细
            pref = preferred_map.get(review.preferred_part_id) if review.preferred_part_id else None
            if pref:
                data["pref_mpn"] = pref.mpn or pref.part_number or ""
                data["pref_brand"] = pref.brand or pref.normalized_brand or ""
                data["pref_category"] = pref.category_level_3 or ""
                data["pref_package"] = pref.package or ""
                data["pref_spec"] = pref.spec_text or ""
                data["pref_cost"] = pref.cost
                data["pref_cost_unit"] = pref.cost_unit or "CNY"
                data["pref_preferred_level"] = pref.preferred_level or "unknown"
                data["pref_control_status"] = pref.control_status or "unknown"
                data["pref_recommendation_reason"] = pref.recommendation_reason or ""

            items.append(data)

        total = len(items)
        preferred_hit = sum(1 for i in items if i["preferred_part_id"])
        summary = {
            "bom_project_id": project.id,
            "project_name": project.project_name or project.filename,
            "total_items": total,
            "preferred_hit_count": preferred_hit,
            "preferred_hit_rate": round(preferred_hit / total, 4) if total else 0,
            "non_preferred_count": sum(1 for i in items if not i["preferred_part_id"]),
            "new_part_count": sum(1 for i in items if i["is_new_part"]),
            "temporary_blocked_count": sum(1 for i in items if i["delivery_control_status"] == "temporary_blocked"),
            "restricted_count": sum(1 for i in items if i["delivery_control_status"] == "restricted"),
            "red_count": sum(1 for i in items if i["selection_risk_level"] == "red"),
            "yellow_count": sum(1 for i in items if i["selection_risk_level"] == "yellow"),
            "alternative_count": sum(1 for i in items if i["recommended_alternatives"]),
        }
        return {"summary": summary, "items": items}
