"""文档上传与解析 API 端点 (T2-012)。

提供文档上传接口，接收非结构化文档（.txt/.md/.pdf），
调用 DocumentParser 服务提取结构化风险事件。

端点:
- POST /api/v1/documents/upload: 上传并解析文档
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["document-upload"])


# ═══════════════════════════════════════════════════════════════════════════════
# 请求/响应模型
# ═══════════════════════════════════════════════════════════════════════════════

class DocumentEvent(BaseModel):
    """单个风险事件。"""
    event_type: str
    title: str
    description: str
    affected_categories: list[str]
    affected_manufacturers: list[str]
    effective_date: Optional[str] = None
    impact_level: str
    price_change_pct: Optional[float] = None
    confidence: float
    evidence_text: str


class DocumentParseResponse(BaseModel):
    """文档解析响应。"""
    success: bool
    events: list[DocumentEvent]
    doc_summary: str
    doc_type_classified: str
    degraded: bool = False
    degrade_reason: str = ""
    latency_ms: float = 0.0
    filename: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# 文本提取
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def _extract_text_from_file(file_content: bytes, filename: str) -> str:
    """从上传的文件中提取文本内容。

    支持 .txt, .md 直接读取文本；.pdf 使用 PyPDF2/pymupdf 提取。

    Args:
        file_content: 文件二进制内容
        filename: 文件名（用于判断格式）

    Returns:
        提取的文本内容

    Raises:
        HTTPException: 不支持的文件格式或提取失败
    """
    ext = Path(filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}",
        )

    if ext in (".txt", ".md"):
        # 直接读取文本
        try:
            return file_content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return file_content.decode("gbk")
            except UnicodeDecodeError:
                return file_content.decode("latin-1")

    if ext == ".pdf":
        return _extract_text_from_pdf(file_content)

    raise HTTPException(status_code=400, detail=f"不支持的文件格式: {ext}")


def _extract_text_from_pdf(file_content: bytes) -> str:
    """从 PDF 文件中提取文本。

    优先使用 PyMuPDF (fitz)，回退到 PyPDF2。

    Args:
        file_content: PDF 文件二进制内容

    Returns:
        提取的文本内容
    """
    # 尝试 PyMuPDF
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_content, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        text = "\n".join(text_parts)
        if text.strip():
            return text
    except ImportError:
        logger.debug("PyMuPDF 未安装，尝试 PyPDF2")
    except Exception as e:
        logger.warning("PyMuPDF 提取失败: %s，尝试 PyPDF2", e)

    # 尝试 PyPDF2
    try:
        import io
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(file_content))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        text = "\n".join(text_parts)
        if text.strip():
            return text
    except ImportError:
        logger.warning("PyPDF2 未安装，PDF 文本提取不可用")
    except Exception as e:
        logger.warning("PyPDF2 提取失败: %s", e)

    raise HTTPException(
        status_code=422,
        detail="PDF 文本提取失败，请确保安装了 PyMuPDF 或 PyPDF2（pip install PyMuPDF 或 pip install PyPDF2）",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/upload", response_model=DocumentParseResponse)
async def upload_and_parse_document(
    file: UploadFile = File(..., description="上传的文档文件（.txt/.md/.pdf）"),
    doc_type: str = Form(default="auto", description="文档类型(auto/price_increase/shortage/report)"),
):
    """上传文档并解析其中的供应链风险事件。

    接收文件后提取文本内容，调用 DocumentParser 服务（LLM或正则降级）
    提取结构化的风险事件列表。

    Args:
        file: 上传的文档文件
        doc_type: 文档类型提示，默认 auto 自动识别

    Returns:
        DocumentParseResponse: 解析结果
    """
    # 验证文件名
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名不能为空")

    # 检查文件大小
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"文件大小超过限制（最大 {MAX_FILE_SIZE // 1024 // 1024}MB）",
        )

    # 提取文本
    text_content = _extract_text_from_file(file_content, file.filename)

    if not text_content.strip():
        raise HTTPException(status_code=400, detail="文档内容为空，无法解析")

    # 验证 doc_type
    valid_doc_types = {"auto", "price_increase", "shortage", "report"}
    if doc_type not in valid_doc_types:
        raise HTTPException(
            status_code=400,
            detail=f"无效的文档类型: {doc_type}，可选值: {', '.join(valid_doc_types)}",
        )

    # 调用 DocumentParser 服务
    try:
        from app.services.llm.document_parser import DocumentParser

        parser = DocumentParser()
        result = parser.parse(text_content=text_content, doc_type=doc_type)
    except Exception as e:
        logger.error("DocumentParser 调用失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"文档解析服务内部错误: {str(e)}",
        )

    # 构造响应
    data = result.data if result.data else {}
    events = data.get("events", [])

    return DocumentParseResponse(
        success=result.success or result.degraded,
        events=events,
        doc_summary=data.get("doc_summary", ""),
        doc_type_classified=data.get("doc_type_classified", "other"),
        degraded=result.degraded,
        degrade_reason=result.degrade_reason,
        latency_ms=result.latency_ms,
        filename=file.filename,
    )
