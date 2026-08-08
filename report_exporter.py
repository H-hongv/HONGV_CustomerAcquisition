"""Enhanced Export — CSV + HTML report + one-click batch operations."""
import csv
import html as html_module
import json
from pathlib import Path
from datetime import datetime
from typing import List


class ReportExporter:
    """Generate comprehensive reports from lead data."""

    def __init__(self, output_dir: str = "exports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_csv(self, companies: List[dict], filename: str = None) -> str:
        """Export companies to CSV with quality fields."""
        if not companies:
            return ""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"leads_{ts}.csv"
        path = self.output_dir / name

        # Gather all possible columns
        columns = [
            "company_name", "country", "website", "grade", "total_score",
            "contact_email", "contact_name", "phone",
            "product", "process", "material", "application", "scale",
            "_authenticity_score", "_completeness_score", "_is_false_positive",
            "signal_details", "discovery_channel", "process_date",
        ]

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for c in companies:
                row = {}
                for col in columns:
                    val = c.get(col, "")
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    row[col] = val
                writer.writerow(row)

        return str(path)

    def export_html_report(self, companies: List[dict], stats: dict = None,
                           cost: dict = None, filename: str = None) -> str:
        """Generate a styled HTML report."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"report_{ts}.html"
        path = self.output_dir / name

        companies_html = self._build_companies_table(companies)
        stats_html = self._build_stats_section(stats or {})
        cost_html = self._build_cost_section(cost or {})

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>外贸获客报告</title>
<style>
body{{font-family:'Microsoft YaHei',sans-serif;max-width:1200px;margin:auto;padding:20px;color:#1E293B;background:#F8FAFC}}
.card{{background:#fff;border-radius:12px;padding:20px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
h1{{color:#2563EB}}h2{{color:#10B981;margin-top:24px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#2563EB;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:6px 12px;border-bottom:1px solid #E2E8F0}}
tr:hover{{background:#F1F5F9}}
.badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold;color:#fff}}
.S{{background:#7C3AED}}.Aplus{{background:#10B981}}.A{{background:#3B82F6}}.B{{background:#F59E0B}}.C{{background:#EF4444}}
.stat{{display:inline-block;margin:0 16px;text-align:center}}.stat-val{{font-size:28px;font-weight:bold}}.stat-label{{font-size:12px;color:#64748B}}
.footer{{text-align:center;color:#94A3B8;font-size:11px;margin-top:40px}}
</style></head>
<body>
<h1>外贸获客自动化报告</h1>
<p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
{stats_html}
{cost_html}
<h2>客户列表</h2>
{companies_html}
<div class="footer">Powered by AI SDR Agent v4.0</div>
</body></html>"""

        path.write_text(html, encoding="utf-8")
        return str(path)

    def _build_companies_table(self, companies: List[dict]) -> str:
        if not companies:
            return "<p>无数据</p>"
        rows = []
        for c in companies[:100]:
            grade = c.get("grade", "")
            score = c.get("total_score", c.get("score", ""))
            auth = c.get("_authenticity_score", "")
            fp = "🚫" if c.get("_is_false_positive") else ""
            grade_cls = grade.replace("+", "plus") if grade else ""
            rows.append(f"""<tr>
<td>{c.get('company_name','')}{fp}</td>
<td>{c.get('country','')}</td>
<td>{score}</td>
<td><span class="badge {grade_cls}">{grade}</span></td>
<td>{auth}</td>
<td style="font-size:11px">{c.get('contact_email',c.get('generic_email',''))[:35]}</td>
<td style="font-size:11px;max-width:200px;overflow:hidden;text-overflow:ellipsis">{c.get('signal_details','')[:80]}</td>
</tr>""")
        return f"<table><thead><tr><th>公司</th><th>国家</th><th>评分</th><th>等级</th><th>质量</th><th>邮箱</th><th>信号</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"

    def _build_stats_section(self, stats: dict) -> str:
        total = stats.get("total", 0)
        by_grade = stats.get("by_grade", {})
        return f"""<div class="card">
<h2>统计概览</h2>
<div><span class="stat"><span class="stat-val" style="color:#2563EB">{total}</span><span class="stat-label">总客户</span></span>
<span class="stat"><span class="stat-val" style="color:#10B981">{by_grade.get('A+',0)}</span><span class="stat-label">A+级</span></span>
<span class="stat"><span class="stat-val" style="color:#3B82F6">{by_grade.get('A',0)}</span><span class="stat-label">A级</span></span>
<span class="stat"><span class="stat-val" style="color:#F59E0B">{by_grade.get('B',0)}</span><span class="stat-label">B级</span></span>
</div></div>"""

    def _build_cost_section(self, cost: dict) -> str:
        dc = cost.get("daily_cost", "0")
        return f"""<div class="card">
<h2>成本分析</h2>
<p>今日成本: {dc} | 总API调用: {sum(cost.get('today_calls',{}).values())}</p>
</div>"""

    def export_roi_report(self, companies: List[dict], stats: dict = None,
                          cost: dict = None, filename: str = None) -> str:
        """ROI 报告: 总线索/合格线索/成本/单线索成本/预估收益/ROI -> CSV + HTML."""
        stats = stats or {}
        cost = cost or {}
        total = int(stats.get("total", len(companies)) or 0)
        qualified = stats.get("qualified")
        if qualified is None:
            grades = [str(c.get("grade", "")) for c in companies]
            qualified = sum(1 for g in grades if g in ("S", "A+", "A"))
        qualified = int(qualified or 0)
        today_cost = self._to_float(cost.get("daily_cost", 0))
        deal_value = self._to_float(stats.get("assumed_deal_value", 10000))
        won_prob = self._to_float(stats.get("won_probability", 0.10))
        expected_revenue = round(qualified * deal_value * won_prob, 2)
        cost_per_lead = round(today_cost / max(total, 1), 4)
        roi = round(expected_revenue / today_cost, 2) if today_cost > 0 else "N/A"

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_name = filename or f"roi_{ts}.csv"
        if not csv_name.lower().endswith(".csv"):
            csv_name += ".csv"
        csv_path = self.output_dir / csv_name
        html_path = self.output_dir / (csv_name[:-4] + ".html")

        metrics = [
            ("total_leads", total, "总线索数"),
            ("qualified_leads", qualified, "合格线索数 (S/A+/A)"),
            ("today_cost", today_cost, "今日成本"),
            ("cost_per_lead", cost_per_lead, "单线索成本"),
            ("assumed_deal_value", deal_value, "预估客单价"),
            ("won_probability", won_prob, "预估成交概率"),
            ("expected_revenue", expected_revenue, "预估收益 = 合格线索 x 客单价 x 概率"),
            ("roi", roi, "ROI = 收益 / 成本 (成本为0时显示 N/A)"),
        ]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value", "note"])
            for metric, value, note in metrics:
                writer.writerow([metric, value, note])
        html_path.write_text(self._build_roi_html(metrics), encoding="utf-8")
        return str(csv_path)

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    def _build_roi_html(self, metrics: list) -> str:
        cards = "".join(
            f"""<div class="card"><h3>{m}</h3><p class="stat-val">{v}</p><p class="stat-label">{note}</p></div>"""
            for m, v, note in metrics
        )
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>ROI 分析报告</title>
<style>
body{{font-family:'Microsoft YaHei',sans-serif;max-width:1200px;margin:auto;padding:20px;color:#1E293B;background:#F8FAFC}}
.card{{background:#fff;border-radius:12px;padding:20px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
h1{{color:#2563EB}}
.stat-val{{font-size:24px;font-weight:bold;color:#2563EB}}
.stat-label{{font-size:12px;color:#64748B}}
.footer{{text-align:center;color:#94A3B8;font-size:11px;margin-top:40px}}
</style></head>
<body>
<h1>ROI 分析报告</h1>
<p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
{cards}
<div class="footer">Powered by AI SDR Agent v4.0</div>
</body></html>"""

    def export_industry_report(self, industry_key: str, performance: dict = None,
                               filename: str = None) -> str:
        """行业洞察报告: 关键词 Top / 邮件统计 / 转化率 / 模型状态 -> HTML."""
        performance = performance or {}
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_key = str(industry_key).replace("\\", "_").replace("/", "_")
        name = filename or f"industry_{safe_key}_{ts}.html"
        if not name.lower().endswith(".html"):
            name += ".html"
        path = self.output_dir / name

        keywords = performance.get("keywords_top") or []
        kw_rows = "".join(f"<tr><td>{html_module.escape(str(k))}</td></tr>" for k in keywords)
        if not kw_rows:
            kw_rows = "<tr><td>暂无沉淀关键词</td></tr>"
        email_stats = performance.get("email_stats") or {}
        sent = email_stats.get("sent", 0)
        replied = email_stats.get("replied", 0)
        bounced = email_stats.get("bounced", 0)
        conversion = performance.get("conversion_rate", "")
        model_status = performance.get("model_status", "未生成")
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>行业洞察报告 - {html_module.escape(str(industry_key))}</title>
<style>
body{{font-family:'Microsoft YaHei',sans-serif;max-width:1200px;margin:auto;padding:20px;color:#1E293B;background:#F8FAFC}}
.card{{background:#fff;border-radius:12px;padding:20px;margin:12px 0;box-shadow:0 1px 3px rgba(0,0,0,.1)}}
h1{{color:#2563EB}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{background:#2563EB;color:#fff;padding:8px 12px;text-align:left}}
td{{padding:6px 12px;border-bottom:1px solid #E2E8F0}}
.stat-val{{font-size:24px;font-weight:bold;color:#10B981}}
.stat-label{{font-size:12px;color:#64748B}}
.footer{{text-align:center;color:#94A3B8;font-size:11px;margin-top:40px}}
</style></head>
<body>
<h1>行业洞察报告 - {html_module.escape(str(industry_key))}</h1>
<p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
<div class="card"><h2>邮件统计</h2>
<span class="stat-val">{html_module.escape(str(sent))}</span><span class="stat-label"> 已发送</span>
<span class="stat-val">{html_module.escape(str(replied))}</span><span class="stat-label"> 已回复</span>
<span class="stat-val">{html_module.escape(str(bounced))}</span><span class="stat-label"> 退信</span>
<p>转化率: {html_module.escape(str(conversion))}</p>
<p>行业模型状态: {html_module.escape(str(model_status))}</p>
</div>
<div class="card"><h2>高绩效关键词 Top</h2>
<table><thead><tr><th>关键词</th></tr></thead><tbody>{kw_rows}</tbody></table>
</div>
<div class="footer">Powered by AI SDR Agent v4.0</div>
</body></html>"""
        path.write_text(html, encoding="utf-8")
        return str(path)

    HUBSPOT_COLUMNS = [
        ("Company Name", "company_name"),
        ("Company Website", "website"),
        ("Deal Name", "company_name"),
        ("Deal Stage", "deal_status"),
        ("Amount", "deal_value"),
        ("Close Date", "closed_at"),
        ("Contact Email", "contact_email"),
        ("Probability", "probability"),
        ("Notes", "notes"),
    ]

    def export_deals_csv(self, deals: List[dict], filename: str = None) -> str:
        """导出商机(deals)全字段 CSV (utf-8-sig, Excel 可开). 空列表返回 ''."""
        if not deals:
            return ""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"deals_{ts}.csv"
        if not name.lower().endswith(".csv"):
            name += ".csv"
        path = self.output_dir / name
        columns = [
            "company_name", "website", "deal_status", "deal_value", "stage",
            "contact_email", "first_contact", "last_activity", "closed_at",
            "probability", "notes",
        ]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for d in deals:
                row = {}
                for col in columns:
                    val = d.get(col, "")
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    row[col] = val
                writer.writerow(row)
        return str(path)

    def export_hubspot_csv(self, deals: List[dict], filename: str = None) -> str:
        """导出 HubSpot 兼容导入 CSV (标准列名). 空列表返回 ''."""
        if not deals:
            return ""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = filename or f"hubspot_{ts}.csv"
        if not name.lower().endswith(".csv"):
            name += ".csv"
        path = self.output_dir / name
        headers = [h for h, _ in self.HUBSPOT_COLUMNS]
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for d in deals:
                row = []
                for _, key in self.HUBSPOT_COLUMNS:
                    val = d.get(key, "")
                    if isinstance(val, (dict, list)):
                        val = json.dumps(val, ensure_ascii=False)
                    row.append(val)
                writer.writerow(row)
        return str(path)

    def export_crm_package(self, deals: List[dict], filename: str = None) -> dict:
        """CRM 导出包: deals CSV + HubSpot CSV + manifest.json."""
        base = filename or "crm_package"
        if base.lower().endswith(".csv"):
            base = base[:-4]
        deals_path = self.export_deals_csv(deals, filename=f"{base}_deals")
        hubspot_path = self.export_hubspot_csv(deals, filename=f"{base}_hubspot")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        manifest = {
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "deal_count": len(deals),
            "format": "hubspot_import",
            "deals_csv": deals_path,
            "hubspot_csv": hubspot_path,
        }
        mpath = self.output_dir / f"{base}_{ts}.json"
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "deals_csv": deals_path,
            "hubspot_csv": hubspot_path,
            "manifest": str(mpath),
        }

    def export_all(self, companies: List[dict], stats: dict = None,
                   cost: dict = None) -> dict:
        """One-click export: CSV + HTML report."""
        csv_path = self.export_csv(companies)
        html_path = self.export_html_report(companies, stats, cost)
        return {"csv": csv_path, "html": html_path}


report_exporter = ReportExporter()
