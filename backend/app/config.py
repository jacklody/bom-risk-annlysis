"""配置更新 — v4.0 改造版"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///data/market_risk.db"
    data_dir: str = "data"

    # ============================================================
    # LLM 配置 — v4.0 改为 DeepSeek（兼容 OpenAI 格式）
    # ============================================================
    llm_provider: str = "deepseek"               # deepseek / openai_compatible
    llm_api_key: str = ""
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-chat"             # deepseek-chat / deepseek-reasoner
    llm_temperature: float = 0.3                 # 分类/抽取类任务用低温度
    llm_timeout: float = 30.0                    # 单次请求超时秒数
    llm_max_tokens: int = 2000

    # 风险引擎参数
    min_confidence_threshold: float = 0.6
    cross_validation_sources: int = 2

    # ============================================================
    # 数据源 API 配置
    # ============================================================

    # Mouser API
    mouser_api_key: str = ""
    mouser_enabled: bool = True

    # LCSC jlcsearch API — 免费免认证
    lcsc_enabled: bool = True
    lcsc_request_delay: float = 0.55

    # 观芯台 — 免登录网页聚合比价
    guanxintai_enabled: bool = True

    # DigiKey API — OAuth2 Client Credentials
    digikey_client_id: str = ""
    digikey_client_secret: str = ""
    digikey_enabled: bool = True

    # Nexar / Octopart — 预留
    nexar_enabled: bool = False
    nexar_client_id: str = ""
    nexar_client_secret: str = ""
    nexar_access_token: str = ""

    # 芯查查 — 预留
    xinchacha_enabled: bool = False
    xinchacha_app_id: str = ""
    xinchacha_app_secret: str = ""

    # 查询配置
    api_query_timeout: float = 10.0
    api_batch_concurrency: int = 5
    cache_ttl_seconds: int = 86400

    # CORS
    cors_allowed_origins: str = "*"

    # 上游原材料价格追踪
    metals_api_key: str = ""
    material_fetch_interval_h: float = 12.0
    material_warning_pct: float = 5.0
    material_alert_pct: float = 10.0
    material_critical_pct: float = 20.0
    rare_earth_amplifier: float = 1.6
    material_tracking_enabled: bool = True

    # ============================================================
    # P1 补充数据源配置 (T2-016)
    # ============================================================

    # SMM 上海有色网 — 付费API
    smm_api_key: str = ""
    smm_enabled: bool = False

    # Mysteel 我的钢铁网 — 付费API
    mysteel_api_key: str = ""
    mysteel_enabled: bool = False

    # LME 伦敦金属交易所 — 网页数据解析
    lme_enabled: bool = False
    lme_data_url: str = "https://www.lme.com/en/prices/reports-and-data"

    # 飞书行情机器人
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""

    # 邮件通知
    notification_email_enabled: bool = False
    notification_email_smtp_host: str = ""
    notification_email_smtp_port: int = 587
    notification_email_username: str = ""
    notification_email_password: str = ""
    notification_email_sender: str = ""
    notification_email_recipients: str = ""
    notification_email_use_tls: bool = True
    notification_email_timeout: float = 10.0

    # ============================================================
    # GDACS 自然灾害数据源配置
    # ============================================================
    gdacs_enabled: bool = True
    gdacs_api_base: str = "https://www.gdacs.org/gdacsapi/api"
    gdacs_event_list_endpoint: str = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/search"
    gdacs_event_detail_endpoint: str = "https://www.gdacs.org/gdacsapi/api/events/geteventdata"
    gdacs_collect_interval_hours: int = 4
    gdacs_min_severity: list[str] = ["Orange", "Red"]
    gdacs_event_types: list[str] = ["earthquake", "flood", "cyclone", "fire", "drought"]
    gdacs_time_window_hours: int = 24
    gdacs_request_timeout: float = 30.0
    gdacs_max_retries: int = 2

    # ============================================================
    # USGS 地震数据源配置
    # ============================================================
    usgs_enabled: bool = True
    usgs_api_endpoint: str = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    usgs_collect_interval_hours: int = 2
    usgs_min_magnitude: float = 5.0
    usgs_direct_impact_km: float = 200.0
    usgs_indirect_impact_km: float = 500.0
    usgs_request_timeout: float = 30.0
    usgs_max_retries: int = 2
    usgs_priority_regions_weight: float = 2.0

    model_config = {"env_file": ".env"}


settings = Settings()
