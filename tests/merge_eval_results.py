"""合并 3 个批次的 CSV + 重新生成总 markdown 报告"""
import csv
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_stream_chat_eval import EvalResult, save_markdown, _qid_in_expected, _category_label


def load_csv(path: str) -> list[EvalResult]:
    out = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row["actual_confidence"] = float(row.get("actual_confidence", 0) or 0)
            row["table_row_count"] = int(row.get("table_row_count", 0) or 0)
            row["chart_generated"] = row.get("chart_generated", "").lower() in ("true", "1", "yes")
            row["elapsed_ms"] = float(row.get("elapsed_ms", 0) or 0)
            out.append(EvalResult(**row))
    return out


def main():
    base = Path("E:/纵联宸捷/首钢项目/会展小镇项目/RAG-Hephaestus-KB-SG-Backend")
    csv_files = [base / "eval_batch1.csv", base / "eval_batch2.csv", base / "eval_batch3.csv"]
    out_csv = base / "eval_full.csv"
    out_md = base / "eval_full.md"

    all_results: list[EvalResult] = []
    for p in csv_files:
        if not p.exists():
            print(f"[WARN] {p} 不存在, 跳过")
            continue
        rs = load_csv(str(p))
        print(f"  [加载] {p.name}: {len(rs)} 条")
        all_results.extend(rs)

    print(f"\n[合并] 共 {len(all_results)} 条用例")

    fieldnames = list(asdict(all_results[0]).keys()) if all_results else []
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in all_results:
            w.writerow(asdict(r))
    print(f"  [CSV] 合并报告: {out_csv}")

    save_markdown(all_results, str(out_md), csv_path=str(out_csv))

    total = len(all_results)
    mode_correct = sum(1 for r in all_results if r.actual_mode == r.expected_mode)
    qid_correct = sum(1 for r in all_results if _qid_in_expected(r.actual_qid, r.expected_qid))
    errored = sum(1 for r in all_results if r.error)
    avg_ms = sum(r.elapsed_ms for r in all_results) / total if total else 0

    print(f"\n========== 总评 ==========")
    print(f"  总用例: {total}")
    print(f"  模式命中: {mode_correct}/{total} ({mode_correct/total*100:.1f}%)")
    print(f"  Q-ID 命中: {qid_correct}/{total} ({qid_correct/total*100:.1f}%)")
    print(f"  错误数: {errored}/{total}")
    print(f"  平均耗时: {avg_ms:.0f}ms")

    by_cat: dict[str, list[EvalResult]] = {}
    for r in all_results:
        by_cat.setdefault(r.category, []).append(r)
    print(f"\n  分类汇总:")
    for cat, rs in by_cat.items():
        mc = sum(1 for r in rs if r.actual_mode == r.expected_mode)
        qc = sum(1 for r in rs if _qid_in_expected(r.actual_qid, r.expected_qid))
        ec = sum(1 for r in rs if r.error)
        am = sum(r.elapsed_ms for r in rs) / len(rs)
        print(f"    {_category_label(cat)}: {len(rs)} 条, 模式 {mc}/{len(rs)}, Q-ID {qc}/{len(rs)}, 错误 {ec}/{len(rs)}, 耗时 {am:.0f}ms")


if __name__ == "__main__":
    main()
