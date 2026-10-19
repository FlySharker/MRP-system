"""FastAPI application entrypoint."""

from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.analysis import AnalysisConfig
from backend.data_local_window import parse_mrp_dates
from backend.forecast import ForecastConfig
from backend.llm_config import load_llm_config, public_llm_config, save_llm_config, test_llm_provider
from backend.service import BackendService

import pandas as pd
import tempfile
import os
import sys
import subprocess


app = FastAPI(title="MRP Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

backend = BackendService()


class AnalysisConfigPayload(BaseModel):
    
    window_size: int = Field(default=5, ge=1, le=20)
    time_window_size: str = Field(default="14D", pattern=r"^\d+[DWMY]$")
    quantile: float = Field(default=0.75, ge=0.5, le=1.0)
    min_interval_len: int = Field(default=1, ge=1, le=10)


    def to_config(self) -> AnalysisConfig:
        return AnalysisConfig(
            window_size=self.window_size,
            time_window_size=self.time_window_size,
            quantile=self.quantile,
            min_interval_len=self.min_interval_len,
        )


class SingleAnalysisRequest(BaseModel):
    material: str = Field(min_length=1)
    include_llm: bool = True
    language: str = Field(default="en")
    llm_provider: str = Field(default="modelscope")
    config: AnalysisConfigPayload = Field(default_factory=AnalysisConfigPayload)


class BatchAnalysisRequest(BaseModel):
    material_prefix: str = "全部"
    statuses: list[str] = Field(default_factory=lambda: ["正常", "异常"])
    max_materials: int = Field(default=20, ge=1, le=100000)
    config: AnalysisConfigPayload = Field(default_factory=AnalysisConfigPayload)


class ForecastRequest(BaseModel):
    material: str = Field(min_length=1)
    horizon_weeks: int = Field(default=12, ge=1, le=52)
    config: AnalysisConfigPayload = Field(default_factory=AnalysisConfigPayload)
    cv_folds: int = Field(default=3, ge=1, le=5)
    auto_seasonal: bool = True
    ensemble: bool = True


class ModelScopeSettingsPayload(BaseModel):
    api_key: str = ""
    base_url: str = "https://api-inference.modelscope.cn/v1/"
    model: str = "deepseek-ai/DeepSeek-V3.2"


class OllamaSettingsPayload(BaseModel):
    host: str = "http://localhost:11434"
    model: str = "qwen2.5:7b"
    keep_alive: str = "5m"


class LocalSettingsPayload(BaseModel):
    model_path: str = "./Qwen2.5-7B-Instruct/Qwen/Qwen2___5-7B-Instruct"
    device_map: str = "auto"
    torch_dtype: Literal["auto", "float16", "bfloat16", "float32"] = "float16"


class LLMConfigPayload(BaseModel):
    enabled: bool = True
    default_provider: Literal["modelscope", "ollama", "local"] = "modelscope"
    default_language: Literal["zh", "en"] = "zh"
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=64, le=8192)
    timeout_seconds: int = Field(default=60, ge=5, le=600)
    retry_count: int = Field(default=1, ge=0, le=5)
    modelscope: ModelScopeSettingsPayload = Field(default_factory=ModelScopeSettingsPayload)
    ollama: OllamaSettingsPayload = Field(default_factory=OllamaSettingsPayload)
    local: LocalSettingsPayload = Field(default_factory=LocalSettingsPayload)


class LLMConfigTestRequest(BaseModel):
    provider: Literal["modelscope", "ollama", "local"] | None = None
    config: LLMConfigPayload | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/overview")
def overview() -> dict:
    return backend.get_overview()


@app.get("/api/materials")
def materials(
    query: str = Query(default="", max_length=100000),
    limit: int = Query(default=20, ge=1, le=100000),
) -> dict[str, list[str]]:
    return {"items": backend.get_materials(query=query, limit=limit)}


@app.get("/api/llm-config")
def get_llm_config() -> dict:
    return public_llm_config(load_llm_config())


@app.post("/api/llm-config")
def update_llm_config(request: LLMConfigPayload) -> dict:
    return save_llm_config(request.model_dump())


@app.post("/api/llm-config/test")
def test_llm_config(request: LLMConfigTestRequest) -> dict:
    overrides = request.config.model_dump() if request.config else None
    return test_llm_provider(provider=request.provider, overrides=overrides)


@app.post("/api/analyze")
def analyze(request: SingleAnalysisRequest) -> dict:
    result = backend.analyze_material(
        material=request.material,
        analysis_config=request.config.to_config(),
        include_llm=request.include_llm,
        language=request.language,
        llm_provider=request.llm_provider,
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("error_message"))
    return result


@app.post("/api/batch-analyze")
def batch_analyze(request: BatchAnalysisRequest) -> dict:
    return backend.analyze_batch(
        material_prefix=request.material_prefix,
        statuses=request.statuses,
        max_materials=request.max_materials,
        analysis_config=request.config.to_config(),
    )


@app.get("/api/forecast/key-materials")
def key_materials(limit: int = Query(default=20, ge=1, le=100000)) -> dict:
    return {"items": backend.get_key_materials(limit=limit)}


@app.post("/api/forecast")
def forecast(request: ForecastRequest) -> dict:
    result = backend.forecast_material(
        material=request.material,
        analysis_config=request.config.to_config(),
        forecast_config=ForecastConfig(
            horizon_weeks=request.horizon_weeks,
            cv_folds=request.cv_folds,
            auto_seasonal=request.auto_seasonal,
            ensemble=request.ensemble,
        ),
    )
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("error_message"))
    return result


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        df = pd.read_excel(tmp_path)
        df.columns = df.columns.map(lambda col: str(col).strip())
        
        required_cols = [
            "Material Number",
            "plant_id",
            "mrp_element_receipt_or_requirement_date",
            "Mrp Element Short Name",
            "Qty",
        ]

        missing = [col for col in required_cols if col not in df.columns]

        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"缺少必要字段: {missing}"
            )
        
        df[['Material Number', 'plant_id']] = df[['Material Number', 'plant_id']].ffill()

        df['mrp_element_receipt_or_requirement_date'] = parse_mrp_dates(
            df['mrp_element_receipt_or_requirement_date']
        )
        
        backend.set_data(df)
        return {
            "status": "success",
            "message": "数据上传成功，已替换当前分析数据源"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.remove(tmp_path)


@app.post("/api/shutdown")
def shutdown() -> dict[str, str]:
    """Shut down the entire application process tree."""
    # Kill all main.exe processes (including PyInstaller bootloader)
    # DETACHED_PROCESS + CREATE_NO_WINDOW prevents a console window from flashing
    startupinfo = subprocess.STARTUPINFO()
    try:
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    except AttributeError:
        pass
    subprocess.Popen(
        ["taskkill", "/F", "/IM", "main.exe"],
        shell=True,
        startupinfo=startupinfo,
    )
    return {"status": "ok"}


# ====== 前端路径（打包兼容写法）======
def get_frontend_path():
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, "frontend")
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))


# ===== frontend=====
frontend_path = get_frontend_path()
out_path = os.path.join(frontend_path, "out")

if os.path.exists(out_path):
    app.mount(
        "/",
        StaticFiles(directory=out_path, html=True),
        name="frontend"
    )
