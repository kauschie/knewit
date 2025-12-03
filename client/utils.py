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

    # Port check
    try:
        port_val = v["server_port"]
        port = int(str(port_val).strip())
        if not (1 <= port <= 65535):
            return False, "Port must be 1-65535."
        # Update the dict with the clean integer to be safe
        v["server_port"] = port
    except Exception:
        return False, "Port must be a valid integer."

    ok, msg = _verify_address(str(v["server_ip"]).strip(), resolve=False)  # flip to True if you want DNS here
    if not ok:
        return False, msg

    un = v.get("username", "")
    if not un:
        return False, "Host name cannot be empty."
    if " " in un:
        un = un.replace(" ", "_")
    if len(un) > 20:
        un = un[:20]
    if "\\" in un or "/" in un:
        un = un.replace("\\", "_").replace("/", "_")

    v["username"] = un

    return True, ""

def _host_validate(v: dict) -> tuple[bool, str]:
    missing = [k.replace("_", " ").title() for k in ("session_id","server_ip","server_port","host_name") if not v[k]]
    if missing:
        return False, f"Please fill: {', '.join(missing)}."

    # Port check (avoid .isdigit pitfalls like leading '+' etc.)
    try:
        port_val = v["server_port"]
        port = int(str(port_val).strip())
        if not (1 <= port <= 65535):
            return False, "Port must be 1-65535."
        # Update the dict with the clean integer to be safe
        v["server_port"] = port
    except Exception:
        return False, "Port must be a valid integer."

    logger.debug(f"Calling _verify_address with ip: {v['server_ip']}")
    ok, msg = _verify_address(str(v["server_ip"]).strip())
    logger.debug(f"_verify_address returned: {ok}, {msg}")
    if not ok:
        return False, msg

    # Normalize host_name spaces -> underscores
    if " " in v.get("host_name", ""):
        v["host_name"] = v["host_name"].replace(" ", "_")
    if not v["host_name"]:
        return False, "Host name cannot be empty."
    if len(v["host_name"]) > 20:
        v["host_name"] = v["host_name"][:20]
    if "\\" in v["host_name"] or "/" in v["host_name"]:
        v["host_name"] = v["host_name"].replace("\\", "_").replace("/", "_")

    return True, ""

# move to server eventually?
def calculate_percent_correct(correct_idx: int, counts: list[int]) -> float:
    """Calculate percentage of answers that matched the correct index."""
    if not counts or correct_idx is None:
        return 0.0
    
    total_responses = sum(counts)
    if total_responses == 0:
        return 0.0
        
    if 0 <= correct_idx < len(counts):
        correct_count = counts[correct_idx]
        return (correct_count / total_responses) * 100.0
        
    return 0.0

def generate_option_labels(count: int) -> list[str]:
    """Generate ['A', 'B', 'C'...] for a given number of options."""
    return [chr(65 + i) for i in range(count)]

def format_leaderboard_row(p: dict, round_target_count: int) -> list:
    """
    Process a player dict into a standardized row for the DataTable.
    Handles score casting, ping validation, and round history padding.
    
    Returns: [ping, name, score(float), correct(int), muted_icon(str), *round_scores(float)]
    """
    # Ping
    # raw_ping = p.get("latency_ms")
    ping = int(p.get("latency_ms", 0)) if str(p.get("latency_ms", "")).isdigit() else p.get("latency_ms", "-")
    
    # Metadata
    name = p.get("player_id", "Unknown")
    
    # Score & Correct (Keep as numbers for correct sorting in DataTable)
    score = float(p.get("score", 0))
    correct = int(p.get("correct_count", 0))
    
    # Muted Status
    is_muted = "🔇" if p.get("is_muted", False) else "🔊"
    
    # Round History (Safety Slice & Pad)
    raw_rounds = p.get("round_scores", [])
    
    # 1. Slice to target
    rounds = [float(v) for v in raw_rounds[:round_target_count]]
    
    # 2. Pad if short
    while len(rounds) < round_target_count:
        rounds.append(0.0)
        
    return [ping, name, score, correct, is_muted, *rounds]