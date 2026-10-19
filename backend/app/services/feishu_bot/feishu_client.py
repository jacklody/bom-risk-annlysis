"""飞书 API 客户端 — 获取 Access Token、发送消息、获取消息内容。"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

FEISHU_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
FEISHU_SEND_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
FEISHU_GET_MSG_URL = "https://open.feishu.cn/open-apis/im/v1/messages/{message_id}"
FEISHU_REPLY_URL = "https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply"


@dataclass
class FeishuMessage:
    """飞书消息结构化对象。"""
    message_id: str = ""
    chat_id: str = ""
    chat_type: str = ""
    msg_type: str = "text"
    content_text: str = ""
    content_json: str = ""
    sender_id: str = ""
    sender_name: str = ""
    create_time: str = ""
    root_id: str = ""  # 话题根消息ID

    @property
    def is_text(self) -> bool:
        return self.msg_type == "text"

    @property
    def is_post(self) -> bool:
        return self.msg_type == "post"

    def get_text(self) -> str:
        """从消息中提取纯文本。"""
        if self.content_text:
            return self.content_text
        if not self.content_json:
            return ""
        try:
            data = json.loads(self.content_json)
            text = data.get("text", "")
            if text:
                return text
            # post 消息：拼接所有文本段落
            content = data.get("content", {})
            paragraphs = []
            for block in content.get("paragraph", []):
                for elem in block.get("elements", []):
                    paragraphs.append(elem.get("text", ""))
            return "".join(paragraphs)
        except (json.JSONDecodeError, KeyError, TypeError):
            return ""


class FeishuClient:
    """飞书开放平台 API 客户端。"""

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        verification_token: str = "",
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self._client

    async def _get_token(self) -> str:
        """获取 tenant_access_token（自动缓存刷新）。"""
        now = time.monotonic()
        if self._token and now < self._token_expiry - 60:
            return self._token

        client = await self._get_client()
        resp = await client.post(
            FEISHU_TOKEN_URL,
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"飞书获取token失败: {data.get('msg', 'unknown')}")
        self._token = data["tenant_access_token"]
        self._token_expiry = now + data.get("expire", 7200)
        return self._token

    async def verify_signature(self, timestamp: str, nonce: str, body: str) -> bool:
        """验证飞书事件回调签名（v1 版本）。"""
        if not self.verification_token:
            return True  # 未配置则跳过验证
        sign = hmac.new(
            key=f"{timestamp}{nonce}{self.verification_token}".encode(),
            msg=body.encode() if isinstance(body, str) else body,
            digestmod=hashlib.sha256,
        ).hexdigest()
        return sign

    async def get_message_content(self, message_id: str) -> str:
        """获取指定消息的原始内容。"""
        token = await self._get_token()
        client = await self._get_client()
        resp = await client.get(
            FEISHU_GET_MSG_URL.format(message_id=message_id),
            headers={"Authorization": f"Bearer {token}"},
        )
        data = resp.json()
        if data.get("code") != 0:
            logger.warning(f"获取飞书消息失败: {data.get('msg')}")
            return ""
        return json.dumps(data.get("data", {}), ensure_ascii=False)

    async def send_message(
        self,
        chat_id: str,
        content: str,
        msg_type: str = "interactive",
        root_id: str = "",
    ) -> bool:
        """发送消息到指定群聊/用户。

        Args:
            chat_id: 群聊ID或用户open_id
            content: 消息内容（text类型为纯文本，interactive类型为卡片JSON）
            msg_type: text / interactive / post
            root_id: 话题根消息ID（回复话题时传入）
        """
        if not self.is_configured:
            logger.warning("飞书客户端未配置，跳过发送消息")
            return False

        token = await self._get_token()
        client = await self._get_client()

        body: dict = {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": content,
        }
        if root_id:
            body["root_id"] = root_id

        try:
            resp = await client.post(
                f"{FEISHU_SEND_MSG_URL}?receive_id_type=chat_id",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            data = resp.json()
            if data.get("code") != 0:
                logger.warning(f"发送飞书消息失败: {data.get('msg')}")
                return False
            logger.info(f"飞书消息发送成功: {data.get('data',{}).get('message_id','')}")
            return True
        except Exception as e:
            logger.error(f"飞书消息发送异常: {e}")
            return False

    async def reply_text(
        self,
        message_id: str,
        text: str,
    ) -> bool:
        """回复文本消息。"""
        if not self.is_configured:
            return False
        token = await self._get_token()
        client = await self._get_client()
        content = json.dumps({"text": text}, ensure_ascii=False)
        try:
            resp = await client.post(
                FEISHU_REPLY_URL.format(message_id=message_id),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"content": content, "msg_type": "text"},
            )
            data = resp.json()
            return data.get("code") == 0
        except Exception as e:
            logger.error(f"飞书回复文本失败: {e}")
            return False

    async def reply_card(
        self,
        message_id: str,
        card_json: str,
    ) -> bool:
        """回复卡片消息。"""
        if not self.is_configured:
            return False
        token = await self._get_token()
        client = await self._get_client()
        try:
            resp = await client.post(
                FEISHU_REPLY_URL.format(message_id=message_id),
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"content": card_json, "msg_type": "interactive"},
            )
            data = resp.json()
            return data.get("code") == 0
        except Exception as e:
            logger.error(f"飞书回复卡片失败: {e}")
            return False

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
