# 龙砺获客自动化系统

## 简介

龙砺获客自动化系统是一个基于AI的智能获客工具，用于自动搜索、分析和筛选金属铸造行业的潜在客户。

## 功能特点

- **双模式运行**：免费模式（DuckDuckGo + trafilatura）和收费模式（Tavily + Firecrawl）
- **多LLM支持**：OpenAI、Gemini、Ollama本地模型
- **智能分析**：自动评分、等级划分、否决条件
- **Web界面**：Streamlit UI，可视化配置和执行

## 评分体系（总分135分）

| 维度 | 分数 | 说明 |
|------|------|------|
| 材质适配性 | 20分 | 金属制品即适配 |
| 工艺需求 | 25分 | 需要打磨/抛光/去毛刺工艺 |
| **意图信号** | **40分** | 核心维度，权重最高 |
| 规模匹配度 | 20分 | 是否有采购能力 |
| 环保加分 | 10分 | 欧洲企业环保要求 |
| 信息完整度 | 5分 | 联系方式完整度 |
| 转化潜力 | 15分 | 综合转化可能性 |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置API Key（可选）

复制 `.env.example` 为 `.env`，填入你的API Key：

```bash
cp .env.example .env
```

### 3. 启动Web界面

```bash
python main.py
```

浏览器自动打开 http://localhost:8501

## 目录结构

```
获客自动化/
├── main.py                    # PyQt5 主入口
├── config.py                   # 配置管理
├── models.py                   # 数据模型
├── pipeline.py                 # 流程编排
├── csv_manager.py              # CSV管理
├── logger.py                   # 日志
├── start.py                    # 快速启动脚本
├── 启动.bat                   # Windows 双击启动
├── .env.example                # 环境变量模板
├── requirements.txt            # 依赖包
│
├── providers/
│   ├── search/                 # 搜索模块
│   │   ├── base.py
│   │   ├── ddg_provider.py     # 免费
│   │   ├── tavily_provider.py  # 收费
│   │   └── factory.py
│   │
│   ├── crawl/                  # 爬取模块
│   │   ├── base.py
│   │   ├── trafilatura_provider.py  # 免费
│   │   ├── firecrawl_provider.py    # 收费
│   │   └── factory.py
│   │
│   ├── verify/                 # 验证模块
│   │   ├── base.py
│   │   ├── dns_provider.py     # 免费
│   │   └── factory.py
│   │
│   └── llm/                    # LLM模块
│       ├── base.py
│       ├── openai_provider.py
│       ├── gemini_provider.py
│       ├── ollama_provider.py
│       └── factory.py
│
└── templates/                  # Prompt模板
```

## 使用方式

### Web界面（推荐）

```bash
python main.py
```

### 命令行

```bash
# 免费模式
python main.py --mode free --country 德国 --count 20

# 收费模式
python main.py --mode paid --country 德国 --count 20
```

## 评分规则

### 意图信号（40分）

**强信号（30-40分）**
- 招聘打磨/抛光/去毛刺工人：40分
- 新建工厂或产线：35分
- 大额投资扩产：35分
- 环保整改/粉尘治理：30分
- 可持续发展报告发布：30分

**中信号（20-30分）**
- IATF16949认证：30分
- 汽车OEM客户：30分
- 行业展会参展：25分
- 新产品线发布：25分
- 获得行业奖项：20分

**弱信号（15-20分）**
- ISO9001认证：20分
- 多年行业经验（20年+）：20分
- 出口业务：15分
- 家族企业：15分
- LinkedIn活跃：15分

### 规模匹配度（20分）

- 大型企业（500+员工）：20分
- 中型企业（100-500员工）：10分
- 小型企业（50-100员工）：5分
- 微型企业（<50员工）：1分

### 等级划分

| 等级 | 分数 | 行动 |
|------|------|------|
| S类 | ≥100分 | 立即重点跟进 |
| A+类 | 85-99分 | 优先开发 |
| A类 | 70-84分 | 常规开发 |
| B类 | 55-69分 | 候选池 |
| C类 | <55分 | 暂不开发 |

## 常见问题

### Q: 如何切换免费/收费模式？

A: 在Web界面侧边栏或配置中心切换。

### Q: 如何自定义提示词？

A: 在"提示词管理"页面编辑。

### Q: 如何调整评分权重？

A: 在"权重调整"页面拖动滑块。

### Q: Ollama如何使用？

A: 
1. 安装Ollama：https://ollama.ai
2. 下载模型：`ollama pull qwen2.5:7b`
3. 在配置中选择 `ollama`

## 技术支持

如有问题，请联系开发团队。

---

*版本：v3.0*
*更新日期：2026-07-09*
