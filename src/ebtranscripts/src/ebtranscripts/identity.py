"""Per-employee / per-machine identity, derived at the edge.

The whole telemetry pipeline had no notion of *who* or *which machine* produced a session —
session identity was the bare Claude Code UUID plus project_slug/cwd/git_branch. For
cross-machine consolidation (a shared Google Drive corpus) and per-machine attribution in
the marts, we derive a stable-per-machine identity here, with zero configuration:

    machine_id  = <hardware serial number>   # ioreg/dmidecode/wmic, stable across rename
    machine     = socket.gethostname()        # short form, `hostname -s`
    drive_user_id = f"{machine_id}:{machine}"   # e.g. "C02XXXXXXXXX:MacBook-Pro-m4"

`drive_user_id()` partitions the Drive directory (abacus/<drive_user_id>/projects/...); the
two components are also stamped onto each derived SessionRecord (machine_id, machine columns)
so the marts can GROUP BY machine.

Why the serial (was `employee_id` = `whoami:hostname`): the hostname breaks on a machine *rename*
(it orphaned
the old Drive dir and split attribution — docs/drive-consolidation-design.md §2b), and the
username leaked a person's login name into the marts. The hardware serial is stable across
renames and carries no username. Trade-offs it introduces, handled elsewhere:
  • It is PERMANENT HARDWARE PII — stripped from any public artifact (the public-demo prune drops
    the machine_id column; the gated internal dashboard keeps it).
  • It is opaque in the dashboard — read it via an internal serial→machine label map if you want
    human-readable names (keep that map internal/gitignored; it's the person-mapping PII).
  • Reading it needs a platform subprocess, so this module is no longer strictly stdlib-only — but
    every lookup is guarded and falls back to "unknown", so extraction never blocks.
"""

from __future__ import annotations

import platform
import socket
import subprocess


def _short_hostname() -> str:
    """The short hostname (`hostname -s`): the first label, no domain suffix."""
    name = socket.gethostname()
    # socket.gethostname() may return an FQDN ("host.local", "host.example.com"); the short
    # form is everything before the first dot, matching `hostname -s`.
    return name.split(".", 1)[0] if name else "unknown"


def _machine_serial() -> str:
    """The hardware serial number, best-effort, never raising.

    Stable across a machine rename (unlike the old employee_id = whoami:hostname — see the
    docstring caveat this replaces). This is the *raw* serial: a permanent hardware identifier,
    so treat it as sensitive — it MUST be stripped from any public artifact (the public demo
    prune drops the machine_id column), and it's opaque in the dashboard without an internal
    serial→machine label map. Requires a platform subprocess (so this module is no longer strictly
    stdlib-only, but every call is guarded and falls back to "unknown" so extraction never blocks).

    Sources, per OS (first that yields a non-empty value wins):
      • macOS   — `ioreg -l` → IOPlatformSerialNumber
      • Linux   — /sys/class/dmi/id/product_serial (often root-only), else `dmidecode`
      • Windows — `wmic bios get serialnumber`
    """

    def _run(cmd: list[str]) -> str:
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            return out.stdout.strip()
        except Exception:
            return ""

    system = platform.system()
    try:
        if system == "Darwin":
            raw = _run(["ioreg", "-l"])
            for line in raw.splitlines():
                if "IOPlatformSerialNumber" in line and '"' in line:
                    # …"IOPlatformSerialNumber" = "C02XXXXXXXXX"
                    return line.rsplit('"', 2)[1] or "unknown"
        elif system == "Linux":
            # Non-root path first: the DMI sysfs file (readable on many distros).
            try:
                with open("/sys/class/dmi/id/product_serial", encoding="utf-8") as fh:
                    val = fh.read().strip()
                    if val:
                        return val
            except Exception:
                pass
            val = _run(["dmidecode", "-s", "system-serial-number"])
            if val:
                return val.splitlines()[-1].strip()
        elif system == "Windows":
            raw = _run(["wmic", "bios", "get", "serialnumber"])
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            # Output is a header "SerialNumber" then the value.
            if len(lines) >= 2:
                return lines[1]
    except Exception:
        pass
    return "unknown"


def machine_identity() -> tuple[str, str]:
    """Return (machine_id, machine) derived from the OS, never raising.

    machine_id is the hardware SERIAL NUMBER (stable across renames), replacing the old
    employee_id/whoami:hostname (which leaked a username and broke on rename). machine stays the
    short hostname (the human-readable half, handy for a serial→machine map). Both fall back to
    "unknown" so identity is best-effort metadata that never blocks extraction.
    """
    machine_id = _machine_serial() or "unknown"
    machine = _short_hostname()
    return machine_id, machine


def drive_user_id(identity: tuple[str, str] | None = None) -> str:
    """The Drive partition key `machine_id:machine` (e.g. "C02XXXXXXXXX:MacBook-Pro-m4")."""
    machine_id, machine = identity if identity is not None else machine_identity()
    return f"{machine_id}:{machine}"
