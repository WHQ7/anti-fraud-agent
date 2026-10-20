"""Explainable, conservative clues. A match is not proof of fraud."""

import re

RULES = (
    ("otp", "索取验证码或密码", "high",
     r"(?:提供|索取|发给|告诉|告知|发送|提交|输入|回传|回复|转发).{0,12}(?:验证码|动态码|密码)|(?:验证码|动态码|密码).{0,10}(?:发给|告诉|发送给|转发给)",
     "对方要求提供或输入认证信息，需要先通过独立渠道核实。"),
    ("transfer", "要求向指定账户转账", "medium",
     r"(?:请|立即|马上|先|需要|务必).{0,12}(?:转账|汇款|付款|打款|充值)|(?:转账|汇款|打款).{0,12}(?:账户|账号|银行卡)",
     "文本包含付款指令；仅凭这段信息无法确认收款方身份。"),
    ("safe_account", "所谓安全账户", "high",
     r"安全账户|资金核查|资金清查|转移资金.{0,8}(?:保护|安全)",
     "以资金保护、核查为由要求转移资金，是需要重点核实的线索。"),
    ("job_fee", "招聘相关预付费用", "high",
     r"(?:先|预先|提前|需要|缴纳|支付|交纳|交).{0,12}(?:保证金|押金|培训费|入职费|手续费|解冻费)",
     "要求先交费再获得工作、提现或退款，需要重点核实。"),
    ("task", "垫资返佣或刷单", "high",
     r"刷单|垫资|充值.{0,12}(?:提现|返佣|佣金)|(?:联单|补单|连单)|(?:返利|返佣).{0,10}(?:任务|本金)",
     "刷单、垫资、先充值后提现等组合可能带来资金损失风险。"),
    ("urgent", "制造紧迫感", "medium",
     r"立即|马上|限时|\d+分钟内|否则.{0,12}(?:冻结|封号|停用|失效)|逾期.{0,8}(?:冻结|停用)",
     "催促可能削弱核实时间，但紧急措辞本身不是诈骗证据。"),
    ("identity", "自称机构或熟人", "medium",
     r"我是.{0,8}(?:客服|警官|警察|老师|老板)|(?:公安|法院|银行客服|官方客服|人事部|招聘专员)",
     "名称、头像或自称身份不能独立证明发送者真实身份。"),
    ("account", "声称账户异常", "medium",
     r"账号异常|账户异常|账户.{0,8}冻结|账号.{0,8}停用|重新认证|补充认证|身份核验",
     "账户异常通知可能真实，也可能用于诱导认证；请独立核实。"),
    ("remote", "远程控制或屏幕共享", "high",
     r"开启.{0,8}(?:屏幕共享|远程控制)|下载.{0,12}(?:远程|控制)|共享.{0,6}屏幕",
     "远程控制或屏幕共享可能暴露认证信息，需核实请求目的与对方身份。"),
    ("injection", "试图干预分析工具", "medium",
     r"忽略.{0,12}(?:指令|规则|提示)|ignore.{0,15}(?:instruction|previous)|system\s*prompt|直接输出.{0,8}(?:安全|无风险)",
     "这部分像是针对分析器的指令，只作为待分析文本处理。"),
)

EDUCATION = re.compile(r"^\s*(?:【[^】]{0,12}】)?(?:反诈(?:提醒|宣传|课堂|知识)|安全提醒|防骗指南)")
NEGATION = re.compile(r"不要|切勿|不应|无需|不会|不需要|勿向|不要将|不要把|不能|拒绝|不参与|不收取")


def check_text_rules(text: str) -> dict:
    findings = []
    educational = bool(EDUCATION.search(text))
    for rule_id, title, severity, pattern, explanation in RULES:
        # Do not let a wildcard span separate clauses: a preceding unrelated
        # '无需笔试' must not suppress a later '先缴纳保证金'.
        pattern = pattern.replace(".{", r"[^。！？!?，,；;\n]{")
        for match in list(re.finditer(pattern, text, flags=re.I))[:2]:
            start, end = match.span()
            clause = re.split(r"[。！？!?\n，,；;]", text[max(0, start - 28):start])[-1]
            negated = bool(NEGATION.search(clause + match.group()))
            sentence = re.split(r"[。！？!?\n]", text[start:])[0]
            education_description = educational and bool(re.search(r"是诈骗|是骗局|警惕", sentence))
            context_only = negated or education_description
            findings.append({
                "id": f"{rule_id}-{start}", "rule_id": rule_id,
                "title": title, "severity": severity,
                "quote": match.group(), "start": start, "end": end,
                "context_only": context_only,
                "explanation": explanation if not context_only else "可能处于否定或安全教育语境，不作为直接风险证据。",
            })
    return {"findings": findings, "educational_context": educational,
            "note": "关键词规则仅提供线索，不能认定身份或诈骗事实。"}
