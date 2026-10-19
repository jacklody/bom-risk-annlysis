"""行情情报收件箱 API。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.upstream.market_inbox_service import MarketInboxService, SubmitNoticePayload

router = APIRouter(prefix="/api/market-inbox", tags=["market-inbox"])


class MarketNoticeSubmitRequest(BaseModel):
    title: str = ""
    raw_text: str = Field(..., min_length=1)
    source_type: str = "manual"
    source_name: str = ""
    source_url: str = ""
    sender: str = ""
    auto_scan: bool = True


class ReviewSignalRequest(BaseModel):
    action: str = Field(..., pattern="^(confirm|reject|observe)$")
    notes: str = ""
    reviewer: str = ""


@router.post("/review/{signal_id}")
def review_signal(signal_id: int, payload: ReviewSignalRequest, db: Session = Depends(get_db)):
    service = MarketInboxService(db)
    result = service.review_signal(signal_id, payload.action, payload.notes, payload.reviewer)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.get("/review-queue")
def list_review_queue(status: str | None = None, db: Session = Depends(get_db)):
    service = MarketInboxService(db)
    return service.list_review_queue(status)


@router.post("/submit")
def submit_market_notice(payload: MarketNoticeSubmitRequest, db: Session = Depends(get_db)):
    service = MarketInboxService(db)
    return service.submit_notice(SubmitNoticePayload(**payload.model_dump()))


@router.get("/")
def list_market_notices(db: Session = Depends(get_db)):
    service = MarketInboxService(db)
    return service.list_notices()


@router.get("/{notice_id}")
def get_market_notice(notice_id: int, db: Session = Depends(get_db)):
    service = MarketInboxService(db)
    result = service.get_notice(notice_id)
    if result is None:
        raise HTTPException(status_code=404, detail="market notice not found")
    return result
