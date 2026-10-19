"""飞书行情机器人 — 群聊监听 → 自动识别行情情报 → 入库。

使用方式:
1. 在飞书开放平台创建企业自建应用
2. 配置权限: im:message, im:message:send_as_bot
3. 配置事件订阅: im.message.receive_v1
4. 设置回调地址: https://your-server/api/feishu/webhook
5. 将机器人添加到目标群聊

详细配置见: docs/FEISHU-BOT-SETUP.md
"""

from app.services.feishu_bot.bot import process_event, get_feishu_client
from app.services.feishu_bot.feishu_client import FeishuClient, FeishuMessage
from app.services.feishu_bot.message_handler import handle_message, is_market_intelligence

__all__ = [
    "process_event",
    "get_feishu_client",
    "FeishuClient",
    "FeishuMessage",
    "handle_message",
    "is_market_intelligence",
]
