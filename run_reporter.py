"""Run report exporter - generates summary reports after each acquisition run."""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from logger import logger

EXPORT_DIR = Path(__file__).parent / "exports"

def generate_run_report(
    country: str,
    industry: str,
    companies: List[Any],
    stats: Dict[str, Any],
    elapsed_seconds: float,
    mode: str = "free",
) -> str:
    """Generate a structured run report and save to exports/.

    Returns:
        Path to the generated report file.
    """
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"run_report_{timestamp}.json"
    filepath = EXPORT_DIR / filename
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "report_type": "acquisition_run",
        "generated_at": now.isoformat(),
        "mode": mode,
        "target": {
            "country": country,
            "industry": industry,
        },
        "results": {
            "total_companies": len(companies),
            "by_grade": stats.get("by_grade", {}),
            "by_country": stats.get("by_country", {}),
        },
        "performance": {
            "elapsed_seconds": round(elapsed_seconds, 1),
            "companies_per_minute": round(len(companies) / max(elapsed_seconds, 1) * 60, 1),
        },
        "companies": [],
    }

    # Add top 10 companies
    for c in companies[:10]:
        report["companies"].append({
            "name": getattr(c, "name", ""),
            "website": getattr(c, "website", ""),
            "country": getattr(c, "country", ""),
            "grade": getattr(c, "grade", ""),
            "total_score": getattr(c, "total_score", 0),
            "email": getattr(c, "contact_email", "") or getattr(c, "generic_email", ""),
        })

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Run report saved: {filepath}")
    return str(filepath)


def generate_txt_report(
    country: str,
    industry: str,
    companies: List[Any],
    stats: Dict[str, Any],
    elapsed_seconds: float,
    mode: str = "free",
) -> str:
    """Generate a human-readable text report."""
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    filename = f"run_report_{timestamp}.txt"
    filepath = EXPORT_DIR / filename
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append("=" * 60)
    lines.append(f"  获客运行报告")
    lines.append(f"  生成时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("=" * 60)
    lines.append(f"  目标国家: {country}")
    lines.append(f"  目标行业: {industry}")
    lines.append(f"  运行模式: {mode}")
    lines.append(f"  耗时: {elapsed_seconds:.1f}s")
    lines.append(f"  获取企业: {len(companies)} 家")
    lines.append(f"  速度: {len(companies)/max(elapsed_seconds,1)*60:.1f} 家/分钟")
    lines.append("")
    lines.append("-" * 40)
    lines.append("  等级分布:")
    for grade, count in stats.get("by_grade", {}).items():
        lines.append(f"    {grade}: {count}")
    lines.append("")
    lines.append("-" * 40)
    lines.append("  Top 10 企业:")
    for i, c in enumerate(companies[:10], 1):
        name = getattr(c, "name", "?")
        grade = getattr(c, "grade", "?")
        score = getattr(c, "total_score", 0)
        country_c = getattr(c, "country", "?")
        lines.append(f"    {i:2}. [{grade}] {name[:50]} ({country_c}, {score}分)")
    lines.append("=" * 60)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Text report saved: {filepath}")
    return str(filepath)
