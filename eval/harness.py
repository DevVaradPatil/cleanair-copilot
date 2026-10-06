"""Evaluation harness: one pipeline config x one question set -> eval/results/<timestamp>_<config>/.

Retrieval metrics need no LLM and always run. --generate adds answer synthesis + the (uncalibrated) faithfulness
judge + rule-based not-found accuracy and must_include checks.
Output: config.yaml (as run), items.jsonl (per question, written as it goes), summary.json, report.md.

Run:
  uv run python -m eval.harness --config configs/ablations/naive.yaml --set golden
  uv run python -m eval.harness --config configs/ablations/naive.yaml --set smoke --generate
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import yaml
from qdrant_client import QdrantClient

from cleanair.config import load_config
from cleanair.pipeline import Copilot
from cleanair.retrieval.filters import filters_for
from cleanair.retrieval.retriever import PipelineRetriever
from cleanair.routing.router import route_rules
from cleanair.settings import Settings
from cleanair.sql.execute import connect_readonly
from cleanair.sql.text_to_sql import answer_data
from eval.judge import faithfulness
from eval.metrics import bootstrap_ci, norm, results_match, retrieval_metrics

GOLDEN = Path("eval/golden/questions.jsonl")
RETRIEVAL_KEYS = ("recall@1", "recall@3", "recall@5", "recall@10", "mrr", "ndcg@5")


def load_set(name: str) -> list[dict]:
    items = [json.loads(line) for line in GOLDEN.read_text(encoding="utf-8").splitlines()]
    return items if name == "golden" else items[::3]  # smoke: every 3rd item, stratified by file order


def needs_retrieval(q: dict) -> bool:
    """Retrieval metrics need evidence; abstention is only meaningful for unanswerable *policy* questions."""
    return bool(q["evidence"]) or (not q["answerable"] and q["route"] != "data")


def evaluate_item(q: dict, retriever: PipelineRetriever, generate: bool, judge_model: str, copilot: Copilot) -> dict:
    cfg = retriever.cfg
    row = {
        "id": q["id"],
        "category": q["category"],
        "answerable": q["answerable"],
        "language": q["language"],
        "gold_route": q["route"],
    }
    if needs_retrieval(q):
        t0 = time.time()
        ranked = retriever.rank(q["question"], filters_for(q["question"], cfg.retrieval.current_only))
        row.update(
            retrieval_s=round(time.time() - t0, 3),
            abstained=not ranked,  # rerank threshold left nothing: "insufficient evidence" without any LLM call
            top=[
                (c.chunk_id, round(c.score_rerank if c.score_rerank is not None else c.score_fused, 4))
                for c in ranked[:10]
            ],
        )
        if q["evidence"]:
            row.update(retrieval_metrics([{"doc_id": c.doc_id, "text": c.text} for c in ranked[:10]], q["evidence"]))
    if not generate:
        return row

    answer, trace = copilot.answer(q["question"])  # the real pipeline: route -> policy/data -> synthesis
    row.update(
        answer=answer.answer,
        not_found=answer.not_found,
        citations=[c.chunk_id for c in answer.citations],
        route_pred=trace.route.route.value,
        gen=trace.generation,
        data_error=trace.data_error,
    )
    if trace.data is not None:
        row.update(sql=trace.data.sql, sql_error=trace.data.error, sql_attempts=trace.data.attempts)
    if q.get("reference_sql"):
        row["sql_correct"] = sql_correct(
            q["reference_sql"], cfg.data.db_path, trace.data.result if trace.data else None
        )
    if q["answerable"]:
        text = norm(answer.answer)
        row["must_include_ok"] = all(norm(m) in text for m in q["must_include"])
        row["false_not_found"] = answer.not_found
        if not answer.not_found:
            score, raw, jusage = faithfulness(q["question"], answer.answer, trace.chunks, judge_model, trace.data)
            row.update(faithfulness=score, judge=raw, judge_usage=jusage)
    else:
        row["not_found_correct"] = answer.not_found
    return row


def sql_correct(reference_sql: str, db_path: str, got) -> bool:
    if got is None:
        return False
    ref_cols, ref_rows = run_reference(reference_sql, db_path)
    ranked = bool(re.search(r"\bLIMIT\s+\d+", reference_sql, re.IGNORECASE))  # a top-k reference
    return results_match(ref_cols, ref_rows, got.columns, [list(r) for r in got.rows], ranked=ranked)


def run_reference(sql: str, db_path: str) -> tuple[list, list]:
    con = connect_readonly(Path(db_path))
    try:
        cur = con.execute(sql)
        return [d[0] for d in cur.description], [list(r) for r in cur.fetchall()]
    finally:
        con.close()


def evaluate_router(items: list[dict], copilot: Copilot) -> list[dict]:
    rows = []
    for q in items:
        out, usage = copilot.route(q["question"])
        rows.append(
            {
                "id": q["id"],
                "category": q["category"],
                "gold_route": q["route"],
                "route_pred": out.route.value,
                "route_ok": out.route.value == q["route"],
                "language": q["language"],
                "language_ok": out.language == q["language"],
                "router_model": usage.get("model"),
                "fallback": usage.get("fallback"),
            }
        )
    return rows


def evaluate_sql(items: list[dict], cfg, sleep_s: float = 0.0) -> list[dict]:
    """Text-to-SQL as a component (SPEC §10.1): data questions only, no synthesis or judge, ~1-3 LLM calls each.
    Correct = result set matches the reference SQL's; for a data-unanswerable item, correct = declared unanswerable.
    An LLM outage on one question is recorded as `llm_error` and excluded from accuracy (it says nothing about SQL)."""
    rows = []
    for q in items:
        time.sleep(sleep_s)  # free tier: stay under the per-minute request cap
        route = route_rules(q["question"])  # cities/time for coverage; routing quality is measured separately
        try:
            out = answer_data(q["question"], cfg, route)
        except RuntimeError as e:  # complete_json gave up: quota / outage
            rows.append({"id": q["id"], "category": q["category"], "llm_error": str(e)})
            print(f"  {q['id']} LLM unavailable: {e}", flush=True)
            continue
        row = {
            "id": q["id"],
            "category": q["category"],
            "sql": out.sql,
            "attempts": out.attempts,
            "error": out.error,
            "unanswerable": out.unanswerable,
            "models": [u.get("model") for u in out.usage],
            "low_coverage": out.low_coverage,
        }
        if q.get("reference_sql"):
            row["sql_correct"] = sql_correct(q["reference_sql"], cfg.data.db_path, out.result)
        else:
            row["sql_correct"] = out.unanswerable
        rows.append(row)
        print(f"  {q['id']} correct={row['sql_correct']} attempts={out.attempts} {out.error or ''}", flush=True)
    return rows


def router_summary(rows: list[dict]) -> dict:
    labels = ["policy", "data", "mixed", "out_of_scope"]
    confusion = {
        g: {p: sum(r["gold_route"] == g and r["route_pred"] == p for r in rows) for p in labels} for g in labels
    }
    acc = bootstrap_ci([float(r["route_ok"]) for r in rows])
    return {
        "route_accuracy": {"mean": round(acc[0], 4), "ci95": [round(acc[1], 4), round(acc[2], 4)], "n": len(rows)},
        "language_accuracy": round(sum(r["language_ok"] for r in rows) / len(rows), 4),
        "confusion (gold -> predicted)": confusion,
    }


def summarize(rows: list[dict]) -> dict:
    def ci(key, subset=rows):
        vals = [float(r[key]) for r in subset if r.get(key) is not None]
        if not vals:
            return None
        mean, lo, hi = bootstrap_ci(vals)
        return {"mean": round(mean, 4), "ci95": [round(lo, 4), round(hi, 4)], "n": len(vals)}

    s = {k: ci(k) for k in RETRIEVAL_KEYS}
    for k in ("faithfulness", "must_include_ok", "false_not_found", "not_found_correct"):
        s[k] = ci(k)
    s["abstain_unanswerable"] = ci("abstained", [r for r in rows if not r["answerable"]])
    s["abstain_answerable"] = ci("abstained", [r for r in rows if r["answerable"]])
    by_cat = defaultdict(list)
    for r in rows:
        by_cat[r["category"]].append(r)
    s["by_category"] = {
        c: {"recall@5": ci("recall@5", rs), "mrr": ci("mrr", rs), "n": len(rs)} for c, rs in by_cat.items()
    }
    s["sql_execution_accuracy"] = ci("sql_correct")
    routed = [r for r in rows if "route_pred" in r]
    if routed:
        s["route_accuracy"] = ci("route_ok", [{**r, "route_ok": r["route_pred"] == r["gold_route"]} for r in routed])
    lat = sorted(r["retrieval_s"] for r in rows if "retrieval_s" in r and "error" not in r) or [0.0]
    s["retrieval_latency_s"] = {
        "p50": lat[len(lat) // 2],
        "p95": lat[min(len(lat) - 1, int(len(lat) * 0.95))],
    }
    gens = [r["gen"] for r in rows if r.get("gen", {}).get("model")]
    if gens:
        s["generation"] = {
            "models": dict(sorted({g["model"]: sum(x["model"] == g["model"] for x in gens) for g in gens}.items())),
            "latency_p50_s": statistics.median(g["latency_s"] for g in gens),
            "cost_usd_total": round(sum(g["cost_usd"] or 0 for g in gens), 4),
        }
    return s


def report_md(name: str, s: dict, n: int) -> str:
    def fmt(m):
        return "—" if not m else f"{m['mean']:.3f} [{m['ci95'][0]:.2f}, {m['ci95'][1]:.2f}] (n={m['n']})"

    lines = [f"# {name}", "", f"{n} questions. 95% bootstrap CIs.", ""]
    if s.get("errors"):
        lines += [
            f"**WARNING: {s['errors']} question(s) errored and are missing from every mean below** "
            "(see `error` in items.jsonl); don't compare this run against others as-is.",
            "",
        ]
    lines += ["| Metric | Value |", "|---|---|"]
    lines += [
        f"| {k} | {fmt(s.get(k))} |"
        for k in (
            *RETRIEVAL_KEYS,
            "faithfulness",
            "must_include_ok",
            "false_not_found",
            "not_found_correct",
            "abstain_unanswerable",
            "abstain_answerable",
            "sql_execution_accuracy",
            "route_accuracy",
        )
    ]
    lines += ["", "| Category | n | recall@5 | MRR |", "|---|---|---|---|"]
    for c, v in s["by_category"].items():
        lines.append(f"| {c} | {v['n']} | {fmt(v['recall@5'])} | {fmt(v['mrr'])} |")
    lines += [
        "",
        f"Retrieval latency: p50 {s['retrieval_latency_s']['p50']} s, p95 {s['retrieval_latency_s']['p95']} s",
    ]
    if "generation" in s:
        g = s["generation"]
        lines += [
            f"Generation: {g['models']}, p50 {g['latency_p50_s']} s, total ${g['cost_usd_total']}",
            "Faithfulness judge is UNCALIBRATED (calibration is M4).",
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Evaluate one pipeline config on the golden set.")
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--set", choices=["golden", "smoke"], default="golden")
    p.add_argument("--out", type=Path, default=Path("eval/results"))
    p.add_argument("--generate", action="store_true", help="also run synthesis + judge (costs LLM calls)")
    p.add_argument("--gen-model", help="override generation.model for this run")
    p.add_argument("--judge-model", default="gemini/gemini-3.1-flash-lite")
    p.add_argument("--limit", type=int, help="first N questions only (pipeline checks)")
    p.add_argument("--router-only", action="store_true", help="evaluate only the config's router (route + language)")
    p.add_argument("--sql-only", action="store_true", help="evaluate only text-to-SQL on the data questions")
    p.add_argument("--sleep", type=float, default=0.0, help="seconds between questions (free-tier rate limits)")
    p.add_argument("--offset", type=int, default=0, help="skip the first N questions (resume across quota days)")
    p.add_argument("--stride", type=int, default=1, help="every Nth question: a small sample across all categories")
    args = p.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    cfg = load_config(args.config)
    if args.gen_model:  # an explicit model for an eval run: no fallback, so one run never mixes two models
        gen = cfg.generation.model_copy(update={"model": args.gen_model, "fallback_model": None})
        cfg = cfg.model_copy(update={"generation": gen})
    items = load_set(args.set)
    if args.sql_only:
        items = [q for q in items if q["category"] == "data" or (q["route"] == "data" and not q["answerable"])]
    items = items[:: args.stride][args.offset :][: args.limit]
    suffix = "router" if args.router_only else "sql" if args.sql_only else args.set
    run_dir = args.out / f"{datetime.now():%Y%m%d-%H%M%S}_{cfg.name}_{suffix}"
    run_dir.mkdir(parents=True)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(cfg.model_dump(), sort_keys=False), encoding="utf-8")

    if args.router_only:
        rows = evaluate_router(items, Copilot(cfg))
        (run_dir / "items.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        s = {
            "config": cfg.name,
            "router": cfg.routing.router,
            "router_model": cfg.routing.model,
            "stride": args.stride,
            "fallbacks_to_rules": sum(r.get("fallback") == "rules" for r in rows),
            **router_summary(rows),
        }
        (run_dir / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
        print(json.dumps(s, indent=1), "\n->", run_dir)
        return 0

    if args.sql_only:
        rows = evaluate_sql(items, cfg, args.sleep)
        (run_dir / "items.jsonl").write_text("".join(json.dumps(r, default=str) + "\n" for r in rows), "utf-8")
        scored = [r for r in rows if "sql_correct" in r]
        acc = bootstrap_ci([float(r["sql_correct"]) for r in scored])
        s = {
            "config": cfg.name,
            "model": cfg.generation.model,
            "n_scored": len(scored),
            "n_llm_errors": len(rows) - len(scored),
            "offset": args.offset,
            "limit": args.limit,
            "sql_execution_accuracy": {"mean": round(acc[0], 4), "ci95": [round(acc[1], 4), round(acc[2], 4)]},
            "first_try": sum(r["attempts"] == 1 and r["sql_correct"] for r in scored),
            "repaired": sum(r["attempts"] > 1 and r["sql_correct"] for r in scored),
            "golden_sha256": hashlib.sha256(GOLDEN.read_bytes()).hexdigest()[:12],
        }
        (run_dir / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
        print(json.dumps(s, indent=1), "\n->", run_dir)
        return 0

    retriever = PipelineRetriever(cfg, QdrantClient(url=Settings().qdrant_url))
    copilot = Copilot(cfg, retriever)
    rows = []
    with open(run_dir / "items.jsonl", "w", encoding="utf-8") as f:
        for i, q in enumerate(items, start=1):
            try:
                row = evaluate_item(q, retriever, args.generate, args.judge_model, copilot)
            except Exception as e:  # one bad LLM response must not lose the whole run; it shows up in items.jsonl
                row = {
                    "id": q["id"],
                    "category": q["category"],
                    "answerable": q["answerable"],
                    "gold_route": q["route"],
                    "error": f"{type(e).__name__}: {e}",
                }
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i}/{len(items)}] {q['id']} recall@5={row.get('recall@5', '-')}", flush=True)

    s = summarize(rows)
    s["errors"] = sum("error" in r for r in rows)
    s["golden_sha256"] = hashlib.sha256(GOLDEN.read_bytes()).hexdigest()[:12]  # which question set produced this
    s.update(
        config=cfg.name,
        set=args.set,
        n=len(rows),
        generate=args.generate,
        collection=cfg.collection,
        judge_model=args.judge_model if args.generate else None,
        limit=args.limit,
    )
    (run_dir / "summary.json").write_text(json.dumps(s, indent=1), encoding="utf-8")
    (run_dir / "report.md").write_text(report_md(f"{cfg.name} on {args.set}", s, len(rows)), encoding="utf-8")
    print((run_dir / "report.md").read_text(encoding="utf-8"))
    print("->", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
