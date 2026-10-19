# GitHub 发布前检查

检查日期：2026-10-19。以下记录基于当前源码；本轮主要修改文档、展示素材、演示数据和忽略规则，没有修改业务逻辑。

## 已完成的整理

- 修正 README 中不存在的 `backend/requirements.txt`，统一为根目录 `requirements.txt`。
- 重写中文首页，提供独立英文说明、技术徽章、项目封面与架构图。
- 新增完全合成的 Excel 演示文件及生成脚本，供首次使用时验证流程。
- 扩充 `.gitignore`：排除依赖、虚拟环境、构建目录、日志、明文模型配置、常见本地数据和模型权重；只放行明确的演示工作簿。
- 核对实际 API、Excel 字段、LLM 调用范围、内存数据生命周期和启动命令。

## 上传前需要确认

| 项目 | 当前情况 | 建议 |
| --- | --- | --- |
| Git 仓库 | 项目使用 Git 管理源码 | 提交前检查暂存区，推送后核对本地与远程提交 |
| 凭据 | 本次发布前已确认 `llm_config.json` 的 API Key 为空，该文件继续被忽略 | 后续填写的凭据仅用于本地运行 |
| 业务记录 | `llm_outputs.txt`、真实数据及历史日志可能包含物料和分析内容 | 不上传；截图和 Issue 仅使用合成或审查后的脱敏数据 |
| 许可证 | 已添加 MIT `LICENSE`，版权署名为 FlySharker | 分发时保留版权及许可声明 |
| 仓库元信息 | 目标仓库为 [FlySharker/MRP-system](https://github.com/FlySharker/MRP-system) | 版本及 CI 徽章在有实际发布或工作流后再添加 |
| 依赖可复现性 | 前端有 lockfile；Python 依赖以最低版本约束为主 | 在目标环境验证后记录兼容版本；不要把一次冒烟验证当作完整依赖兼容性保证 |

`.gitignore` 只影响尚未跟踪的文件，不能清除已经提交的密钥或 Git 历史。上传前检查暂存区中的实际内容。自定义文件名的数据、模型和配置也需要人工复核。

若通过网页上传，不要直接拖入整个项目文件夹：网页上传不会按本地 `.gitignore` 自动筛选。建议使用 Git 暂存检查后推送。

### 建议的本地检查流程

尚未初始化仓库时，手动执行：

```powershell
git init
git check-ignore -v llm_config.json llm_outputs.txt node_modules frontend/node_modules frontend/out
git add .
git status --short
git diff --cached --stat
git diff --cached --name-only
```

确认暂存内容只包含准备发布的源码和文档，再执行提交及远程推送。`llm_config.json`、历史输出、依赖和构建产物均不属于发布源码。

<a id="runtime-limitations"></a>

## 已知运行与部署限制

这些是当前代码中的实际行为，应在改为多人服务或公网部署前处理。

| 优先级 | 发现 | 源码依据与影响 |
| --- | --- | --- |
| 高 | API 没有登录和权限控制，CORS 允许任意来源 | `backend/app.py`：配置读取、修改、测试、上传、分析和关闭接口均未加鉴权；当前应保留本机访问方式 |
| 高 | 关闭接口按进程名终止 `main.exe` | `backend/app.py` 的 `/api/shutdown` 调用 `taskkill /F /IM main.exe`，可能终止同名无关程序；前端 `page-close-handler.tsx` 在 `beforeunload` 时发送该请求，刷新和离开页面也可能触发 |
| 高 | 同一物料跨工厂会被合并 | `backend/service.py` 按 `Material Number` 过滤，批量规则按物料分组；当前需先筛选工厂或使用唯一物料标识 |
| 中 | 上传提示允许 CSV，但实现只读取 Excel | `frontend/app/page.tsx` 的文件选择框接受 `.csv`，`backend/app.py` 仅调用 `pd.read_excel`；文档明确要求 `.xlsx` |
| 中 | 上传和退出使用固定本机 URL | 上传使用 `http://localhost:8000`，关闭使用 `http://127.0.0.1:8000`；远程客户端和改端口场景需改造后验证 |
| 中 | 上传数据与分析历史仅在共享进程内存中 | `BackendService` 使用缓存和内存历史；重启丢失，多人共用时会互相替换数据，多 worker 不共享状态 |
| 中 | 文件上传没有显式大小上限 | 上传路由一次读取完整文件；多人部署应加入体积、格式和资源限制 |
| 中 | LLM 配置是明文文件 | `backend/llm_config.py` 保存 JSON；API 隐藏 Key 不等于文件加密或访问控制 |
| 中 | 本地模型连接测试未运行完整推理 | 测试检查目录及依赖导入；模型能否加载、显存和推理结果需另行验证 |
| 低 | 部分规则说明文案与名称不对应 | `frontend/public/locales/zh/common.json` 中下降趋势、需求激增和延迟供应的解释存在错位；应以规则实现为准，后续统一界面文案 |
| 低 | 静态页面导航时部分预取请求返回 404 | 本轮浏览器日志出现 `__next.*.__PAGE__.txt` 预取 404；页面回退后可正常展示和分析，仍需单独核对 Next.js 静态导出与 FastAPI 路径兼容性 |
| 低 | 根目录 Node 清单与前端清单并存 | 主前端位于 `frontend/package.json`；本轮保留原文件，安装步骤明确进入 `frontend` |

云端解释会发送异常物料的序列与上下文。README 将其列为可选功能；截图与验证没有请求云端模型。

## 本轮验证范围

具体执行结果见 [VALIDATION.md](VALIDATION.md)。外部模型推理、完整 Python 全依赖安装、Windows 可执行文件、多人部署和公网安全性不在此次文档验证范围内。
