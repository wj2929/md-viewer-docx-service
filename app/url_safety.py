import ipaddress
import socket
from typing import Optional
from urllib.parse import urlparse


MARKDOWN_SUFFIXES = (".md", ".markdown", ".txt")
TEXT_CONTENT_TYPES = ("text/markdown", "text/x-markdown", "text/plain")


def _is_blocked_for_strict(ip: ipaddress._BaseAddress) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve_host_ips(host: str) -> list[ipaddress._BaseAddress]:
    try:
        literal = ipaddress.ip_address(host)
        return [literal]
    except ValueError:
        pass

    addresses = []
    for item in socket.getaddrinfo(host, None):
        raw_ip = item[4][0]
        addresses.append(ipaddress.ip_address(raw_ip))
    return addresses


def _content_type_is_markdown(content_type: Optional[str]) -> bool:
    if not content_type:
        return False
    normalized = content_type.split(";", 1)[0].strip().lower()
    return normalized in TEXT_CONTENT_TYPES


def _path_has_markdown_suffix(path: str) -> bool:
    return path.lower().endswith(MARKDOWN_SUFFIXES)


def assert_safe_source_url(
    url: str,
    *,
    policy: str,
    allowlist_hosts: Optional[list[str]] = None,
    content_type: Optional[str] = None,
    validate_markdown_hint: bool = True,
) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("source url must use http or https")
    if not parsed.hostname:
        raise ValueError("source url host is required")

    host = parsed.hostname.lower()
    policy = policy or "local-friendly"

    if policy == "allowlist":
        allowed = {item.strip().lower() for item in allowlist_hosts or [] if item.strip()}
        if host not in allowed:
            raise ValueError(f"source url host is not allowlisted: {host}")
    elif policy == "strict":
        for ip in _resolve_host_ips(host):
            if _is_blocked_for_strict(ip):
                raise ValueError(f"source url resolves to blocked address: {ip}")
    elif policy != "local-friendly":
        raise ValueError(f"unknown source url policy: {policy}")

    if validate_markdown_hint and not _path_has_markdown_suffix(parsed.path):
        if not _content_type_is_markdown(content_type):
            raise ValueError("source url must point to markdown text")
