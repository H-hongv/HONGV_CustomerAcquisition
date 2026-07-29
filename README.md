# 外贸获客自动化系统

## 简介

外贸获客自动化系统是一个基于AI的智能获客工具，用于自动搜索、分析和筛选金属铸造行业的潜在客户。
本项目是一个开放式的多agent协同的获客系统，可以根据行业具体需要来进行针对性的修改。评分权重模型和筛选机制均可以自主配置。

## 功能特点

- **双模式运行**：免费模式（DuckDuckGo + trafilatura）和收费模式（Tavily + Firecrawl）
- **多LLM支持**：OpenAI、deepseek、Gemini
- **智能分析**：自动评分、等级划分、否决条件


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

### 意图信号（自定义配置项）

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

<img width="1195" height="831" alt="2" src="https://github.com/user-attachments/assets/4a5706d5-6ef6-4de7-9d7d-ff277d6a82c4" />
主要接入的mcp适配免费收费双模式

用配置好的某行业筛选配置筛选得到的潜在客户csv，下一步就能通过gmail批量开发功能导入csv实现个性化自定义开发信询盘。

## 技术支持

如有问题，请联系开发团队。

---

*版本：v3.0*
*更新日期：2026-07-09*
