"""Pure helpers for the console. Records stay in the browser session, not disk."""

import copy
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from uuid import uuid4

CHANNELS = ("短信", "邮件", "聊天消息", "网址", "其他")
REVIEW_STATES = ("待复核", "已核实", "误报标记")
DEFAULT_POLICY = {
    "high_priority": True, "medium_priority": True,
    "ask_for_context": True, "display_url_details": True,
}
MAX_RECORDS = 50
SHANGHAI = timezone(timedelta(hours=8))


def now_label() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S")


def validate_policy(policy: dict) -> dict:
    if not isinstance(policy, dict) or set(policy) != set(DEFAULT_POLICY):
        raise ValueError("策略字段不完整。")
    if any(type(value) is not bool for value in policy.values()):
        raise ValueError("策略选项必须为布尔值。")
    return dict(policy)


def review_action(report: dict, policy: dict) -> str:
    if report.get("needs_review"):
        return "冲突复核"
    if report["risk_level"] == "高风险" and policy["high_priority"]:
        return "优先核实"
    if report["risk_level"] == "中风险" and policy["medium_priority"]:
        return "建议核实"
    if report["risk_level"] == "信息不足" and policy["ask_for_context"]:
        return "补充信息"
    return "留意来源"


def make_record(report: dict, channel: str, policy: dict, *, demo: bool = False,
                title: str = "") -> dict:
    if channel not in CHANNELS:
        raise ValueError("不支持的来源渠道。")
    policy = validate_policy(policy)
    return {
        "id": uuid4().hex[:10], "time": now_label(), "channel": channel,
        "title": (title or report["analyzed_text"].replace("\n", " ")[:45] or "未命名信息")[:60],
        "risk_level": report["risk_level"], "mode": report["mode"],
        "mode_label": report["mode_label"], "action": review_action(report, policy),
        "review_state": "待复核", "demo": bool(demo),
        "policy_snapshot": policy, "report": copy.deepcopy(report),
    }


def append_record(records: list[dict], record: dict) -> list[dict]:
    return [*records, record][-MAX_RECORDS:]


def filter_records(records: list[dict], *, channel="全部渠道", risk="全部风险",
                   review="全部状态", keyword="", days: int | None = None) -> list[dict]:
    result = []
    cutoff = datetime.now(SHANGHAI) - timedelta(days=days) if days else None
    for record in reversed(records):
        if channel != "全部渠道" and record["channel"] != channel:
            continue
        if risk != "全部风险" and record["risk_level"] != risk:
            continue
        if review != "全部状态" and record["review_state"] != review:
            continue
        if keyword.strip().casefold() not in (record["title"] + record["report"]["summary"]).casefold():
            continue
        if cutoff and datetime.strptime(record["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=SHANGHAI) < cutoff:
            continue
        result.append(record)
    return result


def stats(records: list[dict]) -> dict:
    levels = Counter(record["risk_level"] for record in records)
    return {
        "total": len(records), "high": levels["高风险"], "medium": levels["中风险"],
        "insufficient": levels["信息不足"], "no_signal": levels["暂未发现明显风险"],
        "pending": sum(record["review_state"] == "待复核" for record in records),
        "reviewed": sum(record["review_state"] == "已核实" for record in records),
        "agent": sum(record["mode"] == "agent" for record in records),
        "fallback": sum(record["mode"] == "fallback" for record in records),
        "urls": sum(len(record["report"]["url_results"]) for record in records),
        "channels": {name: sum(record["channel"] == name for record in records) for name in CHANNELS},
    }


def csv_export(records: list[dict]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["编号", "检测时间", "渠道", "内容摘要", "风险提示", "分析方式", "核实建议", "人工状态", "数据类型"])
    for record in records:
        row = [record["id"], record["time"], record["channel"], record["title"], record["risk_level"],
               record["mode_label"], record["action"], record["review_state"], "虚构演示" if record["demo"] else "会话检测"]
        # Neutralize spreadsheet formulas, including after leading whitespace.
        writer.writerow(["'" + str(value) if str(value).lstrip().startswith(("=", "+", "-", "@")) else value for value in row])
    return stream.getvalue().encode("utf-8-sig")


def safe_log(records: list[dict]) -> str:
    lines = ["辨信 / 实际执行记录", "仅包含事件元数据，不输出原始消息、API 密钥或请求头。", ""]
    for record in reversed(records):
        lines.append(f"[{record['time']}] {record['id']} | {record['channel']} | {record['risk_level']} | "
                     f"{record['mode_label']} | {'虚构演示' if record['demo'] else '会话检测'}")
        for event in record["report"]["trace"]:
            lines.append(f"  {event['step']:02d} [{event['actor']}/{event['status']}] {event['tool']} | {event['detail']}")
        lines.append("")
    if not records:
        lines.append("尚无检测执行记录。运行一次检测后，这里才会出现真实事件。")
    return "\n".join(lines)
