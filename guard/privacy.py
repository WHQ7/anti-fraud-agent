"""Best-effort local redaction, not a guarantee of anonymization."""

import re


def redact(text: str) -> tuple[str, int]:
    count = 0

    def replace(pattern: str, replacement: str, flags: int = 0) -> None:
        nonlocal text, count
        text, found = re.subn(pattern, replacement, text, flags=flags)
        count += found

    replace(r"(?<![A-Za-z0-9_])(?:sk|ghp|github_pat)-?[A-Za-z0-9_]{16,}(?![A-Za-z0-9_])", "[密钥已隐藏]")
    replace(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/-]{8,}=*", r"\1[令牌已隐藏]")
    replace(r"(?im)((?:api[_ -]?key|apikey|password|密码|密钥)\s*[:=：]\s*)[^\s,;，；\"']+",
            r"\1[敏感值已隐藏]")
    replace(r"((?:https?|hxxps?)://)[^/\s?#]*@", r"\1redacted-user@", re.I)
    replace(r"([?&](?:token|access_token|secret|session|sid|code|password|api_key)=)[^&#\s]+",
            r"\1redacted", re.I)
    replace(r"(?<![A-Za-z0-9])(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", "[手机号已隐藏]")
    replace(r"(?<!\d)\d{17}[0-9Xx](?!\d)", "[证件号已隐藏]")
    def email_replacement(match):
        nonlocal count
        # Do not mistake the sanitized userinfo@host of a URL for an email:
        # that would destroy the hostname needed for static inspection.
        prefix = text[max(0, match.start() - 9):match.start()]
        if match.group().startswith("redacted-user@") and re.search(r"(?:https?|hxxps?)://$", prefix, re.I):
            return match.group()
        count += 1
        return "[邮箱已隐藏]"

    text = re.sub(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", email_replacement, text)
    replace(r"((?:验证码|校验码|动态码|OTP)\s*(?:是|为|[:：=])?\s*)\d{4,8}(?!\d)",
            r"\1[验证码已隐藏]", re.I)
    replace(r"(?<!\d)\d{16,19}(?!\d)", "[长数字已隐藏]")
    return text, count
