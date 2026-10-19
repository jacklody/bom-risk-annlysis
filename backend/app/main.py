from contextlib import asynccontextmanager
from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.database import init_db
from app.config import settings

logger = logging.getLogger(__name__)

# 前端构建产物目录（开发时从 backend/ 向上找 frontend/dist）
FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动：初始化数据库 + 供应数据服务 + 原材料价格服务
    init_db()
    
    # v3.3: 供应数据服务生命周期
    from app.api.risk_analysis import get_supply_data_service, ensure_supply_data_service_initialized
    supply_svc = get_supply_data_service()
    try:
        await ensure_supply_data_service_initialized(supply_svc)
        logger.info("SupplyDataService initialized via lifespan")
    except Exception as e:
        logger.warning(f"SupplyDataService initialization failed (will retry on-demand): {e}")
    
    # v3.4: 原材料价格追踪服务生命周期
    try:
        from app.services.material_price_service import get_material_price_service
        from app.services.upstream.risk_context_builder import set_material_tracker
        
        material_price_svc = get_material_price_service()
        # 预取一次基础金属价格以填充缓存
        from app.knowledge.material_mapping import get_material_keys_for_domain
        metals_keys = get_material_keys_for_domain("metals")
        if metals_keys:
            await material_price_svc.get_prices(metals_keys)
        logger.info("MaterialPriceService initialized via lifespan")
        # 注入 tracker 到 risk_context_builder（数据库 session 在请求级别创建）
        set_material_tracker(None)  # 占位，实际 tracker 在 API 层按需创建
    except Exception as e:
        logger.warning(f"MaterialPriceService initialization skipped: {e}")
    
    yield
    
    # 关闭：清理连接
    try:
        shutdown = getattr(supply_svc, "shutdown", None)
        if shutdown:
            await shutdown()
            logger.info("SupplyDataService shutdown complete")
    except Exception as e:
        logger.warning(f"SupplyDataService shutdown error: {e}")
    
    try:
        from app.services.material_price_service import shutdown_material_price_service
        await shutdown_material_price_service()
    except Exception as e:
        logger.warning(f"MaterialPriceService shutdown error: {e}")


app = FastAPI(
    title="BOM风险分析器",
    version="4.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()] if settings.cors_allowed_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.api import events, bom_upload, risk_analysis, bom_project, intel_watch, market_inbox, preferred_library, market_trends, supply, market_intel, dashboard, material_alerts, material_ws, feishu_webhook, risk_chain
from api.v1.delivery_risk import router as delivery_risk_router
from api.v1.project_review import router as project_review_router

app.include_router(risk_chain.router)
app.include_router(events.router, prefix="/api/events", tags=["events"])
app.include_router(bom_upload.router, prefix="/api/bom", tags=["bom"])
app.include_router(risk_analysis.router, prefix="/api/risk", tags=["risk"])
app.include_router(bom_project.router, prefix="/api/bom", tags=["projects"])
app.include_router(intel_watch.router, prefix="/api/intel", tags=["intel"])
app.include_router(market_inbox.router)
app.include_router(preferred_library.router)
app.include_router(market_trends.router, prefix="/api/market-trends", tags=["market-trends"])
app.include_router(supply.router, prefix="/api/supply", tags=["supply"])
app.include_router(market_intel.router)
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(material_alerts.router, tags=["material-alerts"])
app.include_router(material_ws.router, tags=["material-alerts"])
app.include_router(delivery_risk_router)
app.include_router(project_review_router)
app.include_router(feishu_webhook.router, prefix="/api/feishu", tags=["feishu"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "4.1.0"}


# ── 静态前端 ──
if FRONTEND_DIST.is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback：非 /api 请求返回 index.html"""
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIST / "index.html")
else:
    @app.get("/{full_path:path}")
    async def frontend_unavailable(full_path: str):
        return {"detail": "Frontend not built. Run `npm run build` in frontend/ first."}
