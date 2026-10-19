<div align="center">

<img src="docs/assets/hero.svg" alt="MRP Insight Console — 库存风险识别、异常解释与补货规划" width="100%" />

# MRP Insight Console

**面向物料需求计划的库存异常分析与预测工作台**

将 Excel 中的 MRP 记录转化为库存曲线、缺料预警和补货参考，支持按需启用大模型解释。

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-16.2-111827?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-149ECA?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
[![License: MIT](https://img.shields.io/badge/License-MIT-22A699)](LICENSE)

[快速开始](#quick-start) · [数据格式](#data-format) · [大模型配置](#llm) · [发布前检查](docs/PUBLISHING.md) · [English](docs/README.en.md)

</div>

> 本项目用于本机交互式分析。规则分析、批量分析和预测可独立使用，无需配置云端 API Key。预测和模型建议应结合实际业务复核。

## ✨ 能做什么

| 功能 | 说明 |
| --- | --- |
| 📥 数据导入与概览 | 上传 Excel，查看物料数量、记录数量、工厂数量、日期范围及最近分析记录 |
| 🔎 单物料异常分析 | 展示库存与动态安全库存曲线，定位缺料区间，计算风险评分 |
| 🧭 异常原因识别 | 通过规则检测渐进性缺料、库存波动、需求突增和供给延迟 |
| 📊 批量筛查 | 按物料前缀和状态筛选，汇总异常比例、原因分布与风险排序 |
| 📈 库存预测 | 界面默认预测未来 12 周（API 支持 1–52 周），提供滚动验证、可选季节性与模型集成、预测区间及补货建议 |
| 🧠 可选 LLM 解释 | 对异常物料调用 ModelScope、Ollama 或本地 Transformers，生成解释和建议 |
| 🌐 中英文界面 | 支持切换界面语言，并单独设置 LLM 输出语言 |

## 🖼️ 工作流程与预览

**导入 Excel → 单物料诊断 / 批量筛查 → 查看预测 → 复核补货建议**

<img src="docs/assets/architecture.svg" alt="系统架构：Excel 经 Next.js 界面上传到 FastAPI，由规则引擎、预测引擎和可选 LLM 处理" width="100%" />

**单物料诊断 · 合成缺料场景**

<img src="docs/assets/diagnostic-preview.jpg" alt="DEMO-SHORTAGE 的实际分析界面，显示库存曲线、安全库存和缺料区间" width="100%" />

<details>
<summary><b>展开更多真实界面：完整诊断、批量筛查与库存预测</b></summary>

**完整诊断结果**

![单物料分析与规则摘要](docs/assets/single-analysis.jpg)

**批量筛查：3 个合成物料中，1 个正常、2 个异常**

![批量统计与风险排序](docs/assets/batch-analysis.jpg)

**未来 12 周库存预测与补货参考**

![DEMO-SPIKE 库存预测](docs/assets/forecast.jpg)

</details>

封面曲线为设计示意图，不代表真实业务数据。文档所附演示工作簿使用完全合成的数据。

<a id="quick-start"></a>

## 🚀 快速开始

### 1. 准备环境

- **Python 3.10+**；建议使用独立的 Python 3.11 环境。
- **Node.js 20.9+** 与 npm，用于安装及构建前端。
- Windows PowerShell 为下方命令的示例环境。

在下载或克隆后的**项目根目录**执行：

```powershell
python --version
node --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

依赖文件位于根目录 `requirements.txt`。其中也包含本地模型所需的 `torch`、`transformers`、`accelerate`，完整安装可能占用较多磁盘空间。使用 NVIDIA GPU 时，请先安装与驱动及 CUDA 环境兼容的 PyTorch 构建。

macOS / Linux 可使用 `source .venv/bin/activate` 激活环境；主 Web 流程以外的 Windows 打包与退出逻辑需要分别适配、验证。

### 2. 构建前端

```powershell
cd frontend
npm ci
npm run build
cd ..
```

前端使用 Next.js 静态导出，构建结果位于 `frontend/out/`。根目录的 Node 依赖不用于这一步；请在 `frontend` 目录安装。

### 3. 启动系统

```powershell
python -m backend.main
```

程序启动 FastAPI，并自动打开 **http://127.0.0.1:8000**。查看交互式 API 文档可访问 **http://127.0.0.1:8000/docs**。

首次启动时没有内置业务数据，概览为空。点击页面右上角 **「导入数据」** 选择文件，再点击 **「分析」** 上传。

### 4. 用演示数据体验

上传 [examples/sample_mrp.xlsx](examples/sample_mrp.xlsx)，然后：

1. 在概览页确认导入了 3 个物料、1 个工厂。
2. 进入「单条分析」，点击「配置」，输入 `DEMO-SHORTAGE`，**关闭 LLM 深度分析**后点击「分析」，查看缺料区间和规则结果。
3. 进入「异常列表」，点击「分析」，比较 `DEMO-STABLE`、`DEMO-SHORTAGE`、`DEMO-SPIKE` 的风险差异。
4. 进入「未来预测」，点击一个关键物料，生成未来 12 周的预测库存与补货参考。

演示数据涵盖 32 周，便于体验预测流程；它用于功能演示，不用于评估模型精度。生成方法见 [examples/README.md](examples/README.md)。

> 上传会替换当前进程中的数据源。上传数据及最近分析历史保存在内存中，服务重启后需要重新上传。源码运行时可在启动终端按 `Ctrl+C` 停止；当前前端也会在页面卸载时请求 Windows 打包应用的关闭接口，刷新/关闭页面的影响见[发布前检查](docs/PUBLISHING.md#runtime-limitations)。

<a id="data-format"></a>

## 📄 Excel 数据格式

当前后端使用 `pandas.read_excel` 读取**第一个工作表**；推荐上传 `.xlsx`。虽然文件选择框允许 `.csv`，后端尚未实现 CSV 解析，请先转为 Excel。

列名必须与下表一致（首尾空格会被清理）：

| 必需列 | 含义 | 示例 |
| --- | --- | --- |
| `Material Number` | 物料编号，建议在 Excel 中保存为文本以保留前导零 | `DEMO-STABLE` |
| `plant_id` | 工厂标识 | `DEMO-PLANT` |
| `mrp_element_receipt_or_requirement_date` | MRP 事件日期；推荐 ISO 日期 | `2026-01-05` |
| `Mrp Element Short Name` | MRP 事件名称，使用代码中定义的名称 | `Stock` / `Order` / `PurRqs` |
| `Qty` | 数值型数量；收货为正，需求为负 | `500` / `-80` |

示例：

| Material Number | plant_id | mrp_element_receipt_or_requirement_date | Mrp Element Short Name | Qty |
| --- | --- | --- | --- | ---: |
| DEMO-STABLE | DEMO-PLANT | 2026-01-05 | Stock | 500 |
| DEMO-STABLE | DEMO-PLANT | 2026-01-06 | Order | -80 |
| DEMO-STABLE | DEMO-PLANT | 2026-01-09 | PurRqs | 100 |

- `Stock` 设置当时的库存基数；其他事件的处理由 [MRP_ELEMENT_MAP](backend/data_local_window.py) 定义。
- 常用需求事件包括 `Order`、`IndReq`；常用供给事件包括 `PurRqs`、`Pl.ord`。请先核对 ERP 导出事件与代码映射，未识别事件不会自动推断含义。
- 物料编号、工厂和日期中的部分空值会被前向填充。上传前仍应清理数据，并保持每个物料的记录连续、日期明确。
- 每个物料至少需要两条记录。预测效果依赖历史长度与数据质量，历史不足时可能回退到简单模型。
- **当前分析按物料编号聚合，不按工厂分组**。同一物料跨工厂使用时，请先筛选单工厂文件或使用唯一物料标识，避免库存被合并。

<a id="llm"></a>

## 🧠 大模型配置（可选）

在左侧 **「大模型配置」** 中启用 LLM，选择默认来源和输出语言，填写参数、保存并测试；在「单条分析」的「配置」中确认本次运行的开关。

| 来源 | 需要准备 | 配置位置 / 说明 |
| --- | --- | --- |
| ModelScope API | Access Token、可用模型名称和外网连接 | API Key、Base URL、模型 ID；默认地址 `https://api-inference.modelscope.cn/v1/` |
| Ollama | 已启动的 Ollama 服务与已拉取的模型 | 默认 Host `http://localhost:11434`；例如先执行 `ollama pull qwen2.5:7b` |
| 本地 Transformers | 本地模型目录及相应 CPU/GPU 资源 | 配置模型路径、设备和精度；CPU 通常选择 `float32` |

**调用范围：** 交互式单物料分析仅在规则判定异常且启用 LLM 时请求模型；批量 API 使用规则分析，预测 API 使用统计预测，不调用 LLM。ModelScope 会接收该次异常分析的物料序列及上下文，请确认业务数据允许外发后启用。

**配置优先级：** `llm_config.json` 已保存字段 > 环境变量默认值 > 内置默认值。根目录 `.env` 不会被后端自动加载。尚未保存界面配置时，可在启动服务的同一 PowerShell 终端设置：

```powershell
$env:MODELSCOPE_ACCESS_TOKEN = "<your-token>"
$env:BASE_URL = "https://api-inference.modelscope.cn/v1/"
$env:MODEL = "<model-id>"
python -m backend.main
```

可用环境变量还包括 `LLM_PROVIDER`、`LLM_LANGUAGE`、`OLLAMA_HOST`、`OLLAMA_MODEL`、`LOCAL_LLM_MODEL_PATH`，完整定义见 [backend/llm_config.py](backend/llm_config.py)。

`llm_config.json` 会以明文保存凭据，已加入 `.gitignore`。配置 API 会隐藏已保存的 Key，但项目目前没有内置登录、角色权限或访问审计；不要直接暴露到公网。详情见[发布前检查](docs/PUBLISHING.md)。本地 Transformers 的「测试」只检查目录和依赖，完整推理仍需在实际分析中验证。

## 🛠️ 开发与构建

两个终端分别运行：

```powershell
# 终端 1：项目根目录
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
# 终端 2：项目根目录
cd frontend
npm run dev
```

打开 **http://localhost:3000**。当前本机流程依赖后端端口 `8000`；上传及退出组件含固定本机地址，修改 API 基地址不足以完成远程部署。

<details>
<summary><b>Windows 可执行文件打包</b></summary>

先构建前端，再在根目录执行：

```powershell
pyinstaller main.spec
```

打包配方包含 `frontend/out/`，输出为 `dist/main.exe`。这是项目现有打包入口；分发前请在干净的目标 Windows 环境中验证上传、分析、模型依赖及退出行为。本轮文档整理未验证完整可执行文件打包。

</details>

<details>
<summary><b>预测滚动回测</b></summary>

```powershell
python -m backend.forecast_backtest --data-path examples/sample_mrp.xlsx --horizon-weeks 4 --min-history-weeks 8 --max-materials 3
```

可通过 `--output-json <path>` 导出报告。演示数据只验证流程；真实模型表现应在独立的历史业务数据上评估。

</details>

## 🗂️ 项目结构

```text
mrp_system/
├── backend/                 # FastAPI、异常规则、预测与 LLM 适配
│   ├── app.py               # API 与静态页面托管
│   ├── service.py           # 数据缓存及分析服务编排
│   ├── data_local_window.py # 事件映射、安全库存与异常规则
│   ├── forecast.py          # 周粒度预测与补货建议
│   └── llm_config.py        # 模型配置和连接检查
├── frontend/                # Next.js + React + TypeScript
│   ├── app/                 # 概览、单例、批量、预测及模型配置页面
│   ├── components/          # 工作台布局与图表
│   └── public/locales/      # 中英文文案
├── docs/                    # 英文文档、发布检查与 README 图片
├── examples/                # 合成 Excel 示例及可复现生成脚本
├── requirements.txt         # Python 依赖
├── main.spec                # Windows PyInstaller 配方
├── PROJECT_FILES.md         # 维护文件导航
└── Readme.md
```

`node_modules/`、`frontend/.next/`、`frontend/out/`、虚拟环境、打包结果、分析日志及本地数据默认不提交。首次运行前需安装依赖并构建前端。

## ❓ 常见问题

| 问题 | 检查方法 |
| --- | --- |
| 启动后没有页面或页面 404 | 在 `frontend` 中运行 `npm ci` 和 `npm run build`，确认存在 `frontend/out/index.html` 后重启后端 |
| 概览为 0，物料列表为空 | 首次启动没有默认数据；选中 Excel 后还需点击「分析」完成上传 |
| 上传报缺少字段或解析失败 | 核对上表五个列名；使用 `.xlsx`、第一个工作表以及数值型 `Qty` |
| Python 报 `str \| None` 类型错误 | 检查是否使用 Python 3.10+，并确认启动命令使用了已激活的虚拟环境 |
| NumPy / pandas 二进制兼容错误 | 在独立虚拟环境中重新安装依赖，避免混用旧 Conda 环境的二进制包 |
| 页面请求 API 失败 | 确认后端运行于本机 `8000` 端口；检查是否误关后端、代理或端口被占用 |
| 正常物料没有 LLM 输出 | 属于预期行为；只有异常物料在启用 LLM 时触发解释 |
| Ollama / 本地模型失败 | 检查服务、模型 ID、目录、依赖、显存及精度设置；本地模型目录检查不代表推理成功 |

