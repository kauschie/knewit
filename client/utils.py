import ipaddress
import re
from common import logger
import socket

_HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

def _is_valid_hostname(name: str, allow_single_label: bool = True) -> bool:
    if not name:
        return False
    if name.endswith("."):
        name = name[:-1]
    if len(name) > 253:
        return False
    parts = name.split(".")
    if len(parts) == 1 and not allow_single_label:
        return False
    for label in parts:
        if not (1 <= len(label) <= 63) or not _HOST_LABEL_RE.match(label):
            return False
    # avoid all-numeric TLDs (helps catch IP-like strings)
    if parts and parts[-1].isdigit():
        return False
    return True
    
    
def _verify_address(host: str, *, resolve: bool = False, timeout: float = 1.0) -> tuple[bool, str]:
    """Validate IPv4/IPv6 literal or hostname. Optionally attempt DNS resolution."""
    if not host:
        return False, "Server host is required."

    h = host.strip()

    # Allow bracketed IPv6: [2001:db8::1]
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]

    # IP literal?
    try:
        ipaddress.ip_address(h)
        return True, ""
    except ValueError:
        pass

    # localhost?
    if h.lower() == "localhost":
        return True, ""

    # Hostname syntax (IDN-aware)
    try:
        puny = h.encode("idna").decode("ascii")
    except UnicodeError:
        return False, "Domain contains invalid characters."

    if not _is_valid_hostname(puny, allow_single_label=True):
        return False, "Server host must be a valid IPv4/IPv6 address or domain name."

    if not resolve:
        return True, ""

    # Optional: try resolving (IPv4/IPv6). Keep it quick and non-fatal.
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        # Using None service is fine; (host, 0) also works.
        socket.getaddrinfo(puny, None, type=socket.SOCK_STREAM)
        return True, ""
    except socket.gaierror:
        return False, "Domain looks valid but did not resolve (check network/DNS)."
    except OSError as e:
        return False, f"Resolution error: {e}"
    finally:
        socket.setdefaulttimeout(old_timeout)

def _student_validate(v: dict) -> tuple[bool, str]:
    missing = [k.replace("_", " ").title() for k in ("session_id","server_ip","server_port","username") if not v.get(k)]
    if missing:
        return False, f"Please fill: {', '.join(missing)}."

    # Port (robust)
    try:
        port = int(str(v["server_port"]).strip())
        if not (1 <= port <= 65535):
            return False, "Port must be an integer between 1 and 65535."
    except (TypeError, ValueError):
        return False, "Port must be an integer between 1 and 65535."

    ok, msg = _verify_address(str(v["server_ip"]).strip(), resolve=False)  # flip to True if you want DNS here
    if not ok:
        return False, msg

    hn = v.get("username", "")
    if " " in hn:
        v["username"] = hn.replace(" ", "_")

    return True, ""

def _host_validate(v: dict) -> tuple[bool, str]:
    missing = [k.replace("_", " ").title() for k in ("session_id","server_ip","server_port","host_name") if not v[k]]
    if missing:
        return False, f"Please fill: {', '.join(missing)}."

    # Port check (avoid .isdigit pitfalls like leading '+' etc.)
    try:
        port = int(str(v["server_port"]).strip())
        if not (1 <= port <= 65535):
            return False, "Port must be an integer between 1 and 65535."
    except (TypeError, ValueError):
        return False, "Port must be an integer between 1 and 65535."

    logger.debug(f"Calling _verify_address with ip: {v['server_ip']}")
    ok, msg = _verify_address(str(v["server_ip"]).strip())
    logger.debug(f"_verify_address returned: {ok}, {msg}")
    if not ok:
        return False, msg

    # Normalize host_name spaces -> underscores
    if " " in v.get("host_name", ""):
        v["host_name"] = v["host_name"].replace(" ", "_")

    return True, ""
