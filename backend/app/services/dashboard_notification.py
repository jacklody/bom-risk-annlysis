from __future__ import annotations

import json
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.config import settings
from app.models.dashboard_notification import DashboardNotificationRecord
from app.services.dashboard_summary import build_dashboard_summary


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_subject(risk_changes: dict) -> str:
    red_count = risk_changes.get("new_red_item_count") or 0
    orange_count = risk_changes.get("new_orange_item_count") or 0
    yellow_count = risk_changes.get("new_yellow_item_count") or 0
    if red_count or orange_count or yellow_count:
        return f"BOM风险变化提醒：新增红色风险{red_count}项，橙色风险{orange_count}项，黄色风险{yellow_count}项"
    return "BOM风险变化提醒：暂无新增红/橙/黄风险"


def _build_body(risk_changes: dict) -> str:
    lines = [
        "BOM 风险变化摘要",
        "",
        risk_changes.get("notification_summary") or "暂无新增红黄风险或近7天活跃事件。",
        "",
        f"新增红色风险：{risk_changes.get('new_red_item_count') or 0} 项",
        f"新增橙色风险：{risk_changes.get('new_orange_item_count') or 0} 项",
        f"新增黄色风险：{risk_changes.get('new_yellow_item_count') or 0} 项",
        f"变化项目：{risk_changes.get('changed_project_count') or 0} 个",
        f"近7天活跃事件：{risk_changes.get('recent_event_count_7d') or 0} 条",
    ]
    projects = risk_changes.get("projects") or []
    if projects:
        lines.extend(["", "变化项目："])
        for project in projects[:5]:
            lines.append(
                f"- {project.get('project_name')}：红色 +{project.get('new_red_count') or 0}，橙色 +{project.get('new_orange_count') or 0}，黄色 +{project.get('new_yellow_count') or 0}"
            )
    events = risk_changes.get("events") or []
    if events:
        lines.extend(["", "新增事件："])
        for event in events[:5]:
            lines.append(f"- {event.get('title')}")
    return "\n".join(lines)


def build_dashboard_notification_preview(db: Session, channel: str = "manual") -> dict:
    summary = build_dashboard_summary(db)
    risk_changes = summary.get("risk_changes") or {}
    ready = bool(risk_changes.get("notification_ready"))
    return {
        "channel": channel or "manual",
        "ready": ready,
        "subject": _build_subject(risk_changes),
        "body": _build_body(risk_changes),
        "risk_changes": risk_changes,
        "actions": [
            {"label": "查看风险仪表盘", "target_route": "/dashboard", "target_query": {}},
            {"label": "查看事件追踪", "target_route": "/events", "target_query": {}},
        ],
        "generated_at": _now_iso(),
    }


def _record_to_history_row(record: DashboardNotificationRecord) -> dict:
    return record.to_dict()


def _parse_email_recipients() -> list[str]:
    return [item.strip() for item in (settings.notification_email_recipients or "").split(",") if item.strip()]


def _email_recipient_summary(recipients: list[str]) -> str:
    return f"{len(recipients)} 个收件人" if recipients else "未配置收件人"


def _email_config_status() -> dict:
    recipients = _parse_email_recipients()
    configured = bool(
        settings.notification_email_enabled
        and settings.notification_email_smtp_host
        and settings.notification_email_smtp_port > 0
        and settings.notification_email_sender
        and recipients
    )
    return {
        "configured": configured,
        "enabled": configured,
        "recipients": recipients,
        "recipient_summary": _email_recipient_summary(recipients),
    }


def list_notification_channels() -> dict:
    email_status = _email_config_status()
    return {
        "channels": [
            {
                "channel": "manual",
                "label": "人工通知",
                "enabled": True,
                "configured": True,
                "external_delivery": False,
                "status": "available",
                "message": "可生成通知内容，由人工复制发送。",
            },
            {
                "channel": "mock",
                "label": "测试通道",
                "enabled": True,
                "configured": True,
                "external_delivery": True,
                "status": "available",
                "message": "仅用于验证发送流程，不会触达外部系统。",
            },
            {
                "channel": "email",
                "label": "邮件",
                "enabled": email_status["enabled"],
                "configured": email_status["configured"],
                "external_delivery": True,
                "status": "available" if email_status["configured"] else "not_configured",
                "message": "邮件通道已配置，可发送真实邮件通知。" if email_status["configured"] else "邮件通道尚未配置，发送会被阻断。",
            },
            {
                "channel": "feishu",
                "label": "飞书",
                "enabled": False,
                "configured": False,
                "external_delivery": True,
                "status": "not_configured",
                "message": "飞书通道尚未配置，发送会被阻断。",
            },
            {
                "channel": "wecom",
                "label": "企业微信",
                "enabled": False,
                "configured": False,
                "external_delivery": True,
                "status": "not_configured",
                "message": "企业微信通道尚未配置，发送会被阻断。",
            },
        ]
    }


def _send_email_notification(preview: dict) -> dict:
    attempted_at = datetime.now(timezone.utc)
    email_status = _email_config_status()
    if not email_status["configured"]:
        return {
            "status": "blocked",
            "delivered": False,
            "external_delivery": False,
            "provider": "email",
            "recipient_summary": "未配置收件人",
            "failure_reason": "email 通道尚未配置，已阻断外发。",
            "message": "email 通道尚未配置，已阻断外发。",
            "last_attempt_at": attempted_at,
            "delivered_at": None,
        }

    recipients = email_status["recipients"]
    recipient_summary = email_status["recipient_summary"]
    message = EmailMessage()
    message["Subject"] = preview["subject"]
    message["From"] = settings.notification_email_sender
    message["To"] = ", ".join(recipients)
    message.set_content(preview["body"])

    try:
        with smtplib.SMTP(
            settings.notification_email_smtp_host,
            settings.notification_email_smtp_port,
            timeout=settings.notification_email_timeout,
        ) as smtp:
            if settings.notification_email_use_tls:
                smtp.starttls()
            if settings.notification_email_username and settings.notification_email_password:
                smtp.login(settings.notification_email_username, settings.notification_email_password)
            smtp.send_message(message)
    except Exception as exc:
        failure_reason = f"SMTP发送失败：{exc}"
        return {
            "status": "failed",
            "delivered": False,
            "external_delivery": True,
            "provider": "email",
            "recipient_summary": recipient_summary,
            "failure_reason": failure_reason,
            "message": failure_reason,
            "last_attempt_at": attempted_at,
            "delivered_at": None,
        }

    return {
        "status": "sent",
        "delivered": True,
        "external_delivery": True,
        "provider": "email",
        "recipient_summary": recipient_summary,
        "failure_reason": None,
        "message": "邮件通知已发送。",
        "last_attempt_at": attempted_at,
        "delivered_at": attempted_at,
    }


def _send_with_channel(channel: str, preview: dict) -> dict:
    normalized_channel = channel or "manual"
    attempted_at = datetime.now(timezone.utc)
    if normalized_channel == "manual":
        if preview["ready"]:
            return {
                "status": "prepared",
                "delivered": False,
                "external_delivery": False,
                "provider": "manual",
                "recipient_summary": "人工发送",
                "failure_reason": None,
                "message": "通知内容已准备完成，请在正式通知通道接入后发送。",
                "last_attempt_at": attempted_at,
                "delivered_at": None,
            }
        return {
            "status": "skipped",
            "delivered": False,
            "external_delivery": False,
            "provider": "manual",
            "recipient_summary": "人工发送",
            "failure_reason": None,
            "message": "暂无可通知的风险变化，已跳过发送准备。",
            "last_attempt_at": attempted_at,
            "delivered_at": None,
        }
    if normalized_channel == "mock":
        if preview["ready"]:
            return {
                "status": "sent",
                "delivered": True,
                "external_delivery": True,
                "provider": "mock",
                "recipient_summary": "测试收件人",
                "failure_reason": None,
                "message": "测试通知已发送，未触达外部系统。",
                "last_attempt_at": attempted_at,
                "delivered_at": attempted_at,
            }
        return {
            "status": "skipped",
            "delivered": False,
            "external_delivery": False,
            "provider": "mock",
            "recipient_summary": "测试收件人",
            "failure_reason": None,
            "message": "暂无可通知的风险变化，已跳过测试发送。",
            "last_attempt_at": attempted_at,
            "delivered_at": None,
        }
    if normalized_channel == "email":
        if not preview["ready"]:
            return {
                "status": "skipped",
                "delivered": False,
                "external_delivery": False,
                "provider": "email",
                "recipient_summary": _email_config_status()["recipient_summary"],
                "failure_reason": None,
                "message": "暂无可通知的风险变化，已跳过邮件发送。",
                "last_attempt_at": attempted_at,
                "delivered_at": None,
            }
        return _send_email_notification(preview)
    return {
        "status": "blocked",
        "delivered": False,
        "external_delivery": False,
        "provider": normalized_channel,
        "recipient_summary": "未配置收件人",
        "failure_reason": f"{normalized_channel} 通道尚未配置，已阻断外发。",
        "message": f"{normalized_channel} 通道尚未配置，已阻断外发。",
        "last_attempt_at": attempted_at,
        "delivered_at": None,
    }


def prepare_dashboard_notification_dispatch(db: Session, channel: str = "manual", idempotency_key: str | None = None) -> dict:
    if idempotency_key:
        existing = db.query(DashboardNotificationRecord).filter(
            DashboardNotificationRecord.idempotency_key == idempotency_key
        ).order_by(DashboardNotificationRecord.id.desc()).first()
        if existing:
            return {
                "status": "suppressed",
                "channel": existing.channel,
                "delivered": bool(existing.delivered),
                "external_delivery": bool(existing.external_delivery),
                "deduplicated": True,
                "duplicated_from_record_id": existing.id,
                "record_id": existing.id,
                "message": "已检测到相同通知键的历史记录，本次通知已抑制。",
                "prepared_at": _now_iso(),
            }

    preview = build_dashboard_notification_preview(db, channel=channel)
    send_result = _send_with_channel(preview["channel"], preview)
    record = DashboardNotificationRecord(
        channel=preview["channel"],
        status=send_result["status"],
        idempotency_key=idempotency_key,
        subject=preview["subject"],
        body=preview["body"],
        preview_json=json.dumps(preview, ensure_ascii=False),
        delivered=1 if send_result["delivered"] else 0,
        external_delivery=1 if send_result["external_delivery"] else 0,
        message=send_result["message"],
        provider=send_result["provider"],
        recipient_summary=send_result["recipient_summary"],
        failure_reason=send_result["failure_reason"],
        retry_count=0,
        last_attempt_at=send_result["last_attempt_at"],
        delivered_at=send_result["delivered_at"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "status": record.status,
        "channel": preview["channel"],
        "delivered": bool(record.delivered),
        "external_delivery": bool(record.external_delivery),
        "deduplicated": False,
        "record_id": record.id,
        "preview": preview,
        "message": record.message,
        "provider": record.provider,
        "recipient_summary": record.recipient_summary,
        "failure_reason": record.failure_reason,
        "retry_count": record.retry_count or 0,
        "last_attempt_at": record.last_attempt_at.isoformat() if record.last_attempt_at else None,
        "delivered_at": record.delivered_at.isoformat() if record.delivered_at else None,
        "prepared_at": record.created_at.isoformat() if record.created_at else _now_iso(),
    }


def list_dashboard_notification_history(db: Session, limit: int = 20) -> dict:
    safe_limit = min(max(limit, 1), 100)
    records = db.query(DashboardNotificationRecord).order_by(DashboardNotificationRecord.id.desc()).limit(safe_limit).all()
    return {"records": [_record_to_history_row(record) for record in records]}
