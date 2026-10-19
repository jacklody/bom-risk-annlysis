"""关注指令接口"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.watch import WatchCommand
from app.services.intel_agent import IntelAgent

router = APIRouter()


@router.post("/watch")
def create_watch(payload: dict, db: Session = Depends(get_db)):
    """提交关注指令"""
    raw_input = payload.get("raw_input", "")
    if not raw_input:
        return {"error": "raw_input is required"}
    agent = IntelAgent(db)
    cmd = agent.execute(raw_input)
    return cmd.to_dict()


@router.get("/watch/history")
def watch_history(db: Session = Depends(get_db)):
    cmds = (
        db.query(WatchCommand)
        .order_by(WatchCommand.created_at.desc())
        .limit(20)
        .all()
    )
    return {"commands": [c.to_dict() for c in cmds]}


@router.get("/watch/{cmd_id}")
def get_watch(cmd_id: int, db: Session = Depends(get_db)):
    cmd = db.query(WatchCommand).filter(WatchCommand.id == cmd_id).first()
    if not cmd:
        return {"error": "Not found"}
    return cmd.to_dict()
