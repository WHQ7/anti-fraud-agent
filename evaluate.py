"""Synthetic LOCAL regression checks, not a real-world accuracy benchmark."""

import json
from pathlib import Path

from guard.agent import analyze


def evaluate():
    cases = json.loads((Path(__file__).parent / "data" / "evaluation.json").read_text(encoding="utf-8"))
    results = []
    for case in cases:
        report = analyze(case["text"])
        results.append({"id": case["id"], "expected": case["expected"],
                        "actual": report["risk_level"], "passed": report["risk_level"] == case["expected"]})
    return {"scope": "本地规则合成回归样例，不代表真实诈骗识别准确率，不评估 DeepSeek",
            "total": len(results), "passed": sum(item["passed"] for item in results), "results": results}


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] == result["total"] else 1)
