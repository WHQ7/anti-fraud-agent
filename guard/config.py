"""Read only explicitly named credentials; never print or persist their values."""

import os
import re


def get_api_key() -> str:
    for name in ("apikey", "DEEPSEEK_API_KEY"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    # A GUI launched before an environment-variable change can have a stale
    # process environment. Read only the user-authorized key, not all variables.
    if os.name == "nt":
        import winreg

        for root, path in (
            (winreg.HKEY_CURRENT_USER, "Environment"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        ):
            try:
                with winreg.OpenKey(root, path) as key:
                    value, _ = winreg.QueryValueEx(key, "apikey")
                if isinstance(value, str) and value.strip():
                    return value.strip()
            except OSError:
                continue
    return ""


def get_model() -> str:
    value = os.getenv("DEEPSEEK_MODEL", "deepseek-flash").strip()
    return value if re.fullmatch(r"[A-Za-z0-9_.:/-]{1,80}", value) else "deepseek-flash"
