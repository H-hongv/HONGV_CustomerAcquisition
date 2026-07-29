"""SDR CLI Entry Point - supports both graph and legacy orchestrator."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import argparse
from logger import ui_log


def run_graph(args):
    """Run with LangGraph-compatible workflow engine."""
    from workflow import run_sdr_workflow, checkpointer

    ui_log.add(f"=== SDR Graph v3.0: {args.country} {args.industry or ''} ===", "INFO")

    state = run_sdr_workflow(
        country=args.country,
        industry=args.industry or "",
        product=args.product or "",
        target_count=args.count,
        mode=args.mode or "free",
    )

    print(f"\nResults:")
    print(f"  Companies: {state.get_company_count()}")
    print(f"  Contacts: {state.get_contact_count()}")
    print(f"  Emails: {len(state.emails)}")
    print(f"  Stage: {state.current_stage}")
    print(f"  Elapsed: {state.elapsed_seconds}s")
    print(f"  Checkpoint: task_id={state.task_id}")

    if state.errors:
        print(f"  Errors: {len(state.errors)}")
        for e in state.errors[-3:]:
            print(f"    - [{e.get('node','?')}] {e.get('message','')}")

    return state


def run_legacy(args):
    """Run with legacy SdrOrchestrator."""
    from workflow.sdr_orchestrator import SdrOrchestrator

    ui_log.add(f"=== SDR Legacy: {args.country} {args.industry or ''} ===", "INFO")

    orch = SdrOrchestrator()
    result = orch.run(
        country=args.country,
        industry=args.industry or "",
        product=args.product or "",
        count=args.count,
    )

    print(f"\nResults:")
    print(f"  Companies: {len(result.get('companies', []))}")
    print(f"  Export: {result.get('export_path', '')}")
    print(f"  Elapsed: {result.get('elapsed_seconds', 0)}s")

    return result


def main():
    parser = argparse.ArgumentParser(description="SDR Agent v3.0 - AI Lead Generation")
    parser.add_argument("--country", "-c", required=True, help="Target country")
    parser.add_argument("--industry", "-i", default="", help="Target industry")
    parser.add_argument("--product", "-p", default="", help="Product description")
    parser.add_argument("--count", "-n", type=int, default=50, help="Target lead count")
    parser.add_argument("--mode", "-m", default="free", choices=["free", "paid"],
                        help="Operation mode")
    parser.add_argument("--engine", "-e", default="graph", choices=["graph", "legacy"],
                        help="Workflow engine: graph (new) or legacy")
    parser.add_argument("--list-runs", action="store_true", help="List saved workflow runs")

    args = parser.parse_args()

    if args.list_runs:
        from workflow import checkpointer
        runs = checkpointer.list_runs(limit=20)
        print(f"\nRecent Workflow Runs ({len(runs)}):")
        print("-" * 80)
        print(f"  {'Task ID':<24} {'Stage':<18} {'Status':<12} {'Leads':>6} {'Time':>8}")
        print("-" * 80)
        for r in runs:
            print(f"  {r['task_id']:<24} {r['current_stage']:<18} "
                  f"{r['status']:<12} {r['company_count']:>6} {r['elapsed_seconds']:>7.1f}s")
        return

    if args.engine == "graph":
        run_graph(args)
    else:
        run_legacy(args)


if __name__ == "__main__":
    main()
