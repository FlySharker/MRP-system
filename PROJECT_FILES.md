# 项目文件导航

本文件说明当前维护的源码与文档；目录名为 `mrp_system`，Python 依赖位于**根目录**。

| 路径 | 用途 |
| --- | --- |
| `Readme.md` | GitHub 中文首页、功能、安装、数据格式及使用说明 |
| `docs/README.en.md` | 英文使用说明 |
| `docs/PUBLISHING.md` | 发布前检查、已知限制及上传注意事项 |
| `docs/VALIDATION.md` | 此次文档整理的验证范围与结果 |
| `docs/assets/` | 自制 SVG 封面、架构图与合成数据界面截图 |
| `examples/sample_mrp.xlsx` | 可直接上传的合成 MRP 演示工作簿 |
| `examples/generate_sample.py` | 使用 openpyxl 重建演示工作簿 |
| `examples/README.md` | 示例场景、数据来源和运行方式 |
| `requirements.txt` | 数据处理、API、统计预测、模型运行及打包的 Python 依赖 |
| `main.spec` | PyInstaller 配方，包含 `frontend/out` 静态页面 |
| `.gitignore` | 排除本地配置、依赖、日志、数据、权重和构建产物 |
| `.gitattributes` | 统一源码换行格式，保持图片和工作簿为二进制文件 |
| `LICENSE` | MIT 许可证，版权署名为 FlySharker |
| `package.json` / `package-lock.json` | 原有根目录 Node 依赖；主前端另有独立清单 |

## 后端

| 文件 | 用途 |
| --- | --- |
| `backend/main.py` | 本机启动入口，启动 Uvicorn 并打开浏览器 |
| `backend/app.py` | FastAPI 路由、Excel 上传、请求校验与静态页面托管 |
| `backend/config.py` | 项目路径和默认参数；默认没有内置数据源 |
| `backend/service.py` | 内存数据缓存、分析历史、单例/批量/预测编排与序列化 |
| `backend/analysis.py` | 单物料安全库存、缺料区间、规则和风险评分计算 |
| `backend/data_local_window.py` | 日期解析、MRP 事件映射、安全库存、异常规则与命令行批处理 |
| `backend/forecast.py` | 周粒度历史、统计预测、验证、区间估计与补货建议 |
| `backend/forecast_backtest.py` | 滚动回测工具，可导出 JSON 报告 |
| `backend/anomaly_reason.py` | LLM 提示词、三种来源适配及模型输出解析 |
| `backend/llm_config.py` | 模型配置默认值、环境变量、JSON 保存、Key 隐藏及连接测试 |
| `backend/download_llm.py` | 基于 ModelScope 的模型下载辅助脚本 |
| `backend/__init__.py` | Python 包标记 |

## 前端

| 路径 | 用途 |
| --- | --- |
| `frontend/app/page.tsx` | 概览与数据上传 |
| `frontend/app/analyze/` | 单物料分析及加载状态 |
| `frontend/app/batch/` | 批量分析及加载状态 |
| `frontend/app/forecast/` | 库存预测界面 |
| `frontend/app/llm-settings/` | 模型来源、参数与连接测试 |
| `frontend/app/layout.tsx` / `globals.css` | 全局布局、样式与提供者 |
| `frontend/components/app-shell.tsx` | 导航、页面标题及工作台框架 |
| `frontend/components/charts/` | 库存、批量与预测图表及公式展示 |
| `frontend/components/page-close-handler.tsx` | 页面卸载时发送关闭请求，行为限制见发布检查 |
| `frontend/components/i18n-provider.tsx` / `language-switcher.tsx` | 国际化提供者与语言切换 |
| `frontend/i18n.ts` / `public/locales/` | 中英文初始化与翻译资源 |
| `frontend/lib/api.ts` | 类型化 API 客户端 |
| `frontend/stores/batch-store.ts` | 批量分析结果的 Zustand 状态 |
| `frontend/types/react-katex.d.ts` | 公式渲染库的 TypeScript 声明 |
| `frontend/package.json` / `package-lock.json` | 主前端依赖及 npm 脚本 |
| `frontend/next.config.js` | 静态导出、图片与 Turbopack 配置 |
| `frontend/tsconfig.json` / `next-env.d.ts` | TypeScript 及 Next.js 类型配置 |
| `frontend/next-i18next.config.js` | 原有中英文 locale 配置 |

## 本地配置与可再生文件

| 路径 | 说明 |
| --- | --- |
| `llm_config.json` | 可能含明文密钥，仅保留本地，不发布 |
| `llm_outputs.txt` | 历史模型输出，可能含业务数据，不发布 |
| `.venv/` / `.venv-docs/` | 本地 Python 环境，不发布；后者用于此次文档验证 |
| `node_modules/` / `frontend/node_modules/` | 可通过对应清单重新安装 |
| `frontend/.next/` / `frontend/out/` | 前端缓存与静态产物，使用 `npm run build` 重新生成 |
| `frontend/tsconfig.tsbuildinfo` | TypeScript 增量缓存 |
| `__pycache__/` / `*.pyc` | Python 字节码缓存 |
| `build/` / `dist/` | PyInstaller 中间产物与可执行文件 |
| `*.log` / `.vscode/` | 本地日志及编辑器设置 |

保留源码、依赖清单、文档和合成示例。真实业务数据、模型权重及凭据需要单独管理。修改目录或入口后请同步更新本文与 README。
