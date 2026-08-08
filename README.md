# 外贸 AI SDR 多 Agent 获客系统

一个配置驱动的 B2B 潜在客户发现与询盘开发平台。系统通过多 Agent 协作完成搜索、爬取、企业画像、意图分析、规则/LLM 评分、CSV 导出、个性化开发信生成和 Gmail 限速发送。

平台不把某个行业的规则写死在代码中。每个行业可独立配置目标客户画像、搜索语句、评分维度、权重、等级阈值、否决条件、Prompt 和数据源。

<img width="1569" height="1029" alt="1" src="https://github.com/user-attachments/assets/02aa965e-a81a-48c4-8c48-501c7c6020ab" />


## 主要能力

- 多 Agent 工作流：ICP、市场、公司画像、联系人、意图、机会、邮件和反馈等角色协作。
- 双模式数据链：免费模式使用无密钥/本地回退源，付费模式叠加 Tavily、SerpAPI、Firecrawl、Apify 等增强源。
- 两种模式均支持自定义 MCP：`stdio`、Streamable HTTP 和 SSE，可按 `search`/`crawl` 类别接入主流程。
- 可配置评分：规则分、LLM 精排、否决条件、置信度和分级阈值。
- 可追溯交付：公司来源、评分结果、CSV、任务报告和日志。
- 开发信闭环：根据公司画像生成多语言个性化草稿，经审核后用 Gmail 应用专用密码批量发送。
- 发布门禁：启动前离线识别 fatal/warning，检查行业模板、评分、LLM、MCP、付费源、Gmail 和明文凭据。

## 快速开始

### 1. 创建环境

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. 配置凭据

复制 `.env.example` 为 `.env`，只填写实际启用的 Provider。真实 API Key 和 Gmail 应用密码不应写入 `settings.json` 或提交到版本库。


## 免费与付费模式

| 能力 | 免费模式 | 付费模式 |
|---|---|---|
| 搜索 | DDG 等默认源 + 可选 MCP/API | 付费 API + 可选 MCP + 回退源 |
| 爬取 | Playwright/Trafilatura 回退链 + 可选 MCP | Firecrawl/Apify 等 + 可选 MCP + 回退链 |
| 策略 | 较低并发、较小页面数 | 更多搜索轮次、深度爬取和交叉验证 |
| 发布门禁 | 无付费 Key 仍可获客 | 必须有付费搜索/爬取源，或 paid MCP |

“免费”指默认数据获取链不强制付费 API，不保证 LLM、网络、邮件或自定义 MCP 零成本，免费模式用于跑通整套流程。
<img width="1569" height="1027" alt="3" src="https://github.com/user-attachments/assets/48f2ed91-c194-47b3-ba88-efeb3568e5cb" />
此为免费模式的某行业示例获取的潜在客户
<img width="1566" height="1017" alt="7" src="https://github.com/user-attachments/assets/9f68c8bb-2ea9-42d9-be9a-b106870faff6" />


## 自定义行业

行业 JSON 位于 `industries/`，也可从设置页的行业向导创建。一个可发布模板至少包含：

- `name` 和 `description`。
- 至少 3 条 `search_queries`，建议包含 `{country}` 和 `{industry}`。
- 非空 `dimensions`，每项有唯一 `key`、`name`、`max_score` 和规则。
- 严格降序且不超过总分的 `grade_thresholds`。
- 可选 `veto_conditions`、行业 Prompt 和发件企业信息。

新行业上线前必须用人工标注样本验证评分和否决逻辑。一个行业的测试结果不能直接代表其他行业。

## 自定义 MCP

每个 MCP 可指定：

- `transport`: `stdio`、`streamable_http`/`http` 或 `sse`。
- `category`: `search` 或 `crawl` 会接入主流程。
- `modes`: `free`、`paid` 或两者。
- `tool_name` 和 `argument_map`: 将系统标准参数映射到自定义工具。
- `env`/`headers`: 用 `${ENV_NAME}` 引用 Secret。

详细配置见 [docs/mcp_configuration.md](docs/mcp_configuration.md)。

## 邮件发送

建议流程是“生成草稿 → 人工审核 → 小批量测试 → 限速发送 → 记录退信/退订/回复”。不要把未审核的全部 CSV 直接发送。上线前还要根据目标市场和自身业务场景确认发信依据、隐私告知、保留期和退订流程。
<img width="1576" height="1017" alt="4" src="https://github.com/user-attachments/assets/a8609a77-61cd-4c47-8351-b7b38ec43927" />


## 跟进与回复闭环 (Phase 2)

发送之后系统可持续跟进并感知回复，形成"发送 → 回复感知 → 跟进 → 学习 → 再搜索"闭环：

- **跟进序列**：`tools/email/followup.py` 提供 D3/D7/D14 跟进，支持 AI 个性化生成（无 LLM 时回退静态模板），并通过 `tools/email/scheduler.py` 后台线程每日触发。App 启动时自动拉起调度器与 IMAP 轮询。
- **配置项**（`settings.json` 的 `followup` 段，均可缺省）：
  - `followup.auto_enabled`：跟进自动开关（默认 `false`，保守起见需手动开启）
  - `followup.run_at`：每日触发时间（默认 `"09:00"`）
  - `followup.dry_run`：预览模式（默认 `true`）
  - `followup.llm_enabled`：AI 跟进模板（默认 `true`）
  - `followup.imap_poll_enabled`：IMAP 回复轮询（默认 `true`）
  - `followup.imap_poll_interval`：轮询间隔秒（默认 `1800`）
- **回复感知**：Gmail IMAP（`GMAIL_EMAIL` + `GMAIL_APP_PASSWORD`）自动分类回复（positive/neutral/negative/auto_reply/bounce）。positive 回复自动创建商机（`deals` 表，stage=replied）并生成回复草稿；退信自动标记并从后续发送剔除。
- **商机看板**：GUI 新增"商机"页，按阶段查看/流转（已回复 → 谈判中 → 成交/流失），成交/流失结果回写公司标签供后续 RAG 引用。
- **A/B 测试闭环**：发送时把模板变体名写入 `email_log.variant`，回复/退信自动回传，形成"变体 → 回复率"报表（GUI 邮件页与 `get_template_report_from_db()`）。
- **关键词自适应**：搜索阶段自动合并 `keyword_performance` 中历史高转化关键词；每 10 轮以上评分数据可触发 `optimize_weights()` 校准评分权重（写入 `scoring.calibrated_weights`，无效时回退默认权重）。
  
欢迎大佬加入到这个项目的完善当中
