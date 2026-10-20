"""Strict validation and plain-text export; never render model text as HTML."""

import json
import re

LEVELS = ("高风险", "中风险", "暂未发现明显风险", "信息不足")
DISCLAIMER = "本结果仅供辅助核实，不是诈骗事实认定或安全保证。网址未被访问，发送者身份未被验证。"


def validate_report(content: str, text: str, allowed_ids: set[str]) -> dict:
    if not isinstance(content, str) or len(content) > 18000:
        raise ValueError("invalid report length")
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("report must be object")
    required = {"risk_level", "summary", "evidence", "recommendations", "uncertainties", "citation_ids"}
    if set(data) != required or data["risk_level"] not in LEVELS:
        raise ValueError("invalid keys or risk level")
    if not isinstance(data["summary"], str) or not 5 <= len(data["summary"]) <= 1200:
        raise ValueError("invalid summary")
    evidence = data["evidence"]
    if not isinstance(evidence, list) or len(evidence) > 10:
        raise ValueError("invalid evidence")
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"quote", "reason"}:
            raise ValueError("invalid evidence keys")
        if not isinstance(item["quote"], str) or not 2 <= len(item["quote"]) <= 500 or item["quote"] not in text:
            raise ValueError("evidence not grounded in input")
        if not isinstance(item["reason"], str) or not 2 <= len(item["reason"]) <= 700:
            raise ValueError("invalid evidence reason")
        item["start"] = text.index(item["quote"])
        item["end"] = item["start"] + len(item["quote"])
    for field in ("recommendations", "uncertainties"):
        if not isinstance(data[field], list) or not 1 <= len(data[field]) <= 8:
            raise ValueError("invalid list")
        if any(not isinstance(value, str) or not 2 <= len(value) <= 700 for value in data[field]):
            raise ValueError("invalid list item")
    citations = data["citation_ids"]
    if (not isinstance(citations, list) or len(citations) > 8
            or any(not isinstance(value, str) or value not in allowed_ids for value in citations)):
        raise ValueError("unretrieved citation")
    if data["risk_level"] in {"高风险", "中风险"} and not evidence:
        raise ValueError("risk needs evidence")
    authored_text = " ".join([data["summary"], *[item["reason"] for item in evidence],
                              *data["recommendations"], *data["uncertainties"]])
    if re.search(r"\d+(?:\.\d+)?\s*[%％]|百分之", authored_text):
        raise ValueError("unverified percentage")
    data["citation_ids"] = list(dict.fromkeys(citations))
    return data


def report_text(report: dict) -> str:
    lines = ["辨信 · 反诈与钓鱼信息分析报告", f"生成时间：{report['created_at']}",
             f"模式：{report['mode_label']}", f"风险提示：{report['risk_level']}",
             "", report["summary"], "", "原文依据（展示经过尽力脱敏的文本片段）"]
    for item in report["evidence"]:
        lines.extend([f"- {item['quote']}", f"  {item['reason']}"])
    lines.extend(["", "建议核实步骤", *[f"- {value}" for value in report["recommendations"]],
                  "", "仍不确定的事项", *[f"- {value}" for value in report["uncertainties"]]])
    lines.extend(["", "网址静态检查（未访问）"])
    for item in report["url_results"]:
        lines.extend([f"- {item['url']}", f"  主机名：{item['hostname']}", *[f"  {value}" for value in item["features"]]])
    lines.extend(["", "参考资料（资料相关，不代表已核实本次事件）"])
    for doc in report["sources"]:
        if doc["id"] in report["citation_ids"]:
            lines.extend([f"[{doc['id']}] {doc['title']}", doc["source_url"], doc["source_scope"]])
    lines.extend(["", "提示", *report["warnings"], DISCLAIMER])
    return "\n".join(lines)
