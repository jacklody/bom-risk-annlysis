from sqlalchemy.orm import Session
from app.models.bom import BomItem, BomProject
from app.services.preferred_library.normalizer import normalize_brand, normalize_mpn


class HistoricalPartIndexer:
    def __init__(self, db: Session):
        self.db = db

    def get_usage(self, item: BomItem) -> dict:
        brand = normalize_brand(item.raw_brand or item.normalized_brand)
        mpn = normalize_mpn(item.raw_part_number or item.raw_spec)
        if not mpn:
            return {"usage_count": 0, "project_count": 0, "project_names": []}
        query = self.db.query(BomItem).filter(BomItem.id != item.id)
        candidates = query.all()
        matched = []
        project_ids = set()
        for candidate in candidates:
            c_brand = normalize_brand(candidate.raw_brand or candidate.normalized_brand)
            c_mpn = normalize_mpn(candidate.raw_part_number or candidate.raw_spec)
            if c_mpn == mpn and (not brand or not c_brand or brand == c_brand):
                matched.append(candidate)
                project_ids.add(candidate.bom_upload_id)
        projects = self.db.query(BomProject).filter(BomProject.id.in_(project_ids)).all() if project_ids else []
        return {
            "usage_count": len(matched),
            "project_count": len(project_ids),
            "project_names": [p.project_name or p.filename for p in projects],
        }
