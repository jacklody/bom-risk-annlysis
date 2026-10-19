from app.database import SessionLocal, init_db
from app.models.bom import BomItem, BomProject, RiskLevel
from app.models.preferred import BomSelectionReview, PreferredPart
from app.services.preferred_library.review_service import PreferredLibraryReviewService


def _clear(db):
    db.query(BomSelectionReview).delete()
    db.query(PreferredPart).delete()
    db.query(BomItem).delete()
    db.query(BomProject).delete()
    db.commit()


def test_review_exact_preferred_match_is_green():
    init_db()
    db = SessionLocal()
    _clear(db)
    try:
        project = BomProject(id=101, filename="new.csv", project_name="新项目", total_items=1)
        item = BomItem(bom_upload_id=101, row_number=1, raw_part_number="D-001", raw_brand="YAGEO", raw_category="二极管", raw_spec="US1M SMA", risk_level=RiskLevel.GREEN)
        preferred = PreferredPart(category_level_3="二极管", brand="YAGEO", normalized_brand="YAGEO", part_number="D-001", mpn="US1M", normalized_mpn="US1M", package="SMA", preferred_level="strong_recommended", control_status="preferred")
        db.add_all([project, item, preferred])
        db.commit()

        result = PreferredLibraryReviewService(db).review_project(101)
        detail = result["items"][0]
        assert result["summary"]["preferred_hit_count"] == 1
        assert detail["match_status"] == "exact_part_number"
        assert detail["selection_risk_level"] == "green"
        assert detail["preferred_level"] == "strong_recommended"
    finally:
        db.close()


def test_review_new_non_preferred_part_is_red_with_alternative():
    init_db()
    db = SessionLocal()
    _clear(db)
    try:
        project = BomProject(id=102, filename="new.csv", project_name="新项目", total_items=1)
        item = BomItem(bom_upload_id=102, row_number=1, raw_part_number="X-NEW", raw_brand="ABC", raw_category="二极管", raw_spec="US1M SMA", risk_level=RiskLevel.GREEN)
        preferred = PreferredPart(category_level_3="二极管", brand="YAGEO", normalized_brand="YAGEO", part_number="D-001", mpn="US1M", normalized_mpn="US1M", package="SMA", preferred_level="strong_recommended", control_status="preferred")
        db.add_all([project, item, preferred])
        db.commit()

        result = PreferredLibraryReviewService(db).review_project(102)
        detail = result["items"][0]
        assert detail["match_status"] == "not_found"
        assert detail["is_new_part"] is True
        assert detail["selection_risk_level"] == "red"
        assert detail["recommended_alternatives"]
    finally:
        db.close()


def test_review_confirmed_long_lead_time_is_temporary_blocked():
    init_db()
    db = SessionLocal()
    _clear(db)
    try:
        project = BomProject(id=103, filename="risk.csv", project_name="风险项目", total_items=1)
        item = BomItem(
            bom_upload_id=103,
            row_number=1,
            raw_part_number="C3225X5R1A226M250AC",
            raw_brand="TDK",
            raw_category="MLCC",
            raw_spec="高容MLCC 22uF 25V",
            risk_level=RiskLevel.RED,
            risk_reason="已确认缺货，交期延长至 16 周",
            lead_time_risk_weeks=16,
            supply_risk_tags="shortage,confirmed",
        )
        db.add_all([project, item])
        db.commit()

        result = PreferredLibraryReviewService(db).review_project(103)
        detail = result["items"][0]
        assert detail["delivery_control_status"] == "temporary_blocked"
        assert "16" in detail["delivery_control_reason"]
        assert detail["selection_risk_level"] == "red"
    finally:
        db.close()
