"""Static URL analysis only. No DNS, HTTP, redirects, sockets or downloads."""

import ipaddress
import re
from urllib.parse import urlsplit

URL_RE = re.compile(r"(?:https?://|hxxps?://|www\.)[^\s<>\"'\u3000，。；！？（）【】]+", re.I)


def extract_urls(text: str) -> list[str]:
    results = []
    for match in URL_RE.finditer(text):
        raw = match.group().rstrip(".,;!?)］]}")
        if raw not in results:
            results.append(raw)
        if len(results) == 8:
            break
    return results


def inspect_url_features(text: str) -> dict:
    results = []
    for raw in extract_urls(text):
        candidate = re.sub(r"^hxxp", "http", raw, flags=re.I)
        if candidate.lower().startswith("www."):
            candidate = "https://" + candidate
        flags = []
        host = ""
        port = None
        scheme = ""
        try:
            parts = urlsplit(candidate)
            host = parts.hostname or ""
            scheme = parts.scheme.lower()
            port = parts.port
            if not host or scheme not in {"http", "https"} or "\\" in candidate:
                raise ValueError("invalid URL")
            if parts.username is not None:
                flags.append("含 @ 用户信息，@ 前的品牌名不是实际主机名。")
            if scheme == "http":
                flags.append("使用 HTTP，不能据此确认通信加密或身份。")
            try:
                address = ipaddress.ip_address(host)
                flags.append("主机直接使用 IP 地址，需核实服务来源。")
                if not address.is_global:
                    flags.append("属于非公网地址；本程序不会访问它。")
            except ValueError:
                if host.lower() == "localhost" or host.lower().endswith(".localhost"):
                    flags.append("本机地址；本程序不会访问它。")
            if any(ord(char) > 127 for char in host) or "xn--" in host.lower():
                flags.append("包含国际化域名或 Punycode，注意相似字符；合法站点也可能使用。")
            if len(host.split(".")) >= 5:
                flags.append("主机名层级较多，不能把前缀误认为所属机构。")
            if len(raw) > 180 or "%" in parts.netloc:
                flags.append("网址较长或主机信息含编码，需仔细核实实际主机名。")
            if port is not None and port not in {80, 443}:
                flags.append("使用非标准端口，需核实用途；这本身不证明恶意。")
        except (ValueError, UnicodeError):
            flags.append("网址格式异常，无法可靠解析。")
        results.append({"url": raw, "hostname": host, "scheme": scheme,
                        "port": port, "features": flags,
                        "visited": False,
                        "note": "仅静态结构分析，未查询信誉、证书或真实网页；HTTPS 也不保证可信。"})
    return {"urls": results, "limit": 8, "network_access": False}
