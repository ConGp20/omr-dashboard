"""Configuration advisor: non-blocking findings, hints and recommendations.

Everything here is advisory. Nothing this module produces prevents an action —
it explains what looks wrong, why it matters, and what to do about it, and the
UI links straight to the page where it can be changed. A dashboard that refuses
to work because a setting is unusual would be worse than one that says so.

Each check is a small pure function over an ``AdvisorContext`` so it can be
tested in isolation without a live VPS, router or database.
"""
from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from schemas import BondState, DashboardStatus, Finding, LinkState, LinkType

# Link types that are typically billed by volume — these are the ones where a
# missing data cap actually costs money.
METERED_TYPES = {LinkType.lte, LinkType.fiveg, LinkType.satellite}

DEFAULT_JWT_SECRET = "change-me-in-production"

# Thresholds for "this link is technically up but not healthy".
POOR_LOSS_PCT = 2.0
POOR_LATENCY_MS = 150.0


@dataclass
class AdvisorContext:
    settings: Any
    status: DashboardStatus
    quotas: dict[str, dict] = field(default_factory=dict)
    usage: dict[str, tuple] = field(default_factory=dict)
    alerts: dict[str, Any] = field(default_factory=dict)
    bind_addr: str = "127.0.0.1"
    # Fraction of the accounting month elapsed (0..1), for volume projection.
    month_progress: float = 1.0


def _finding(fid: str, severity: str, title: str, detail: str, action: str,
             page: Optional[str], category: str) -> Finding:
    return Finding(id=fid, severity=severity, title=title, detail=detail,
                   action=action, page=page, category=category)


# --------------------------------------------------------------------------- #
# Security
# --------------------------------------------------------------------------- #
def check_jwt_secret(ctx: AdvisorContext) -> list[Finding]:
    if ctx.settings.demo or ctx.settings.jwt_secret != DEFAULT_JWT_SECRET:
        return []
    return [_finding(
        "jwt_default", "error", "Sitzungsschlüssel ist noch der Platzhalter",
        "JWT_SECRET steht auf dem Auslieferungswert. Wer ihn kennt, kann sich "
        "gültige Sitzungen selbst ausstellen und käme ohne Passwort hinein.",
        "Unter System → Sicherheit einen langen Zufallswert setzen. Alle "
        "offenen Sitzungen werden dabei abgemeldet.",
        "/system", "security")]


def check_dashboard_password(ctx: AdvisorContext) -> list[Finding]:
    if ctx.settings.demo:
        return []
    if ctx.settings.dashboard_pass or ctx.settings.omr_admin_key:
        return []
    return [_finding(
        "no_password", "warn", "Kein Dashboard-Passwort gesetzt",
        "Ohne Passwort ist die Anmeldung offen — jeder, der das Dashboard "
        "erreicht, hat vollen Zugriff auf VPS und Router.",
        "Unter System → Sicherheit ein Passwort vergeben.",
        "/system", "security")]


def _is_public(addr: str) -> bool:
    """Whether binding to ``addr`` exposes the dashboard beyond the tunnel."""
    if addr in ("0.0.0.0", "::", ""):
        return True
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False  # a hostname — can't judge, stay quiet rather than cry wolf
    return not (ip.is_loopback or ip.is_private or ip.is_link_local)


def check_bind_address(ctx: AdvisorContext) -> list[Finding]:
    if ctx.settings.demo or not _is_public(ctx.bind_addr):
        return []
    where = "alle Schnittstellen" if ctx.bind_addr in ("0.0.0.0", "::") else ctx.bind_addr
    return [_finding(
        "bind_public", "error", "Dashboard ist öffentlich erreichbar",
        f"BIND_ADDR steht auf {where}. Das Dashboard ist damit aus dem Internet "
        "erreichbar, obwohl es für den Management-Tunnel gedacht ist.",
        "BIND_ADDR in der .env auf die WireGuard-Tunnel-IP setzen "
        "(z. B. 10.255.247.1) und den Stack neu starten.",
        None, "security")]


def check_router_credentials(ctx: AdvisorContext) -> list[Finding]:
    if ctx.settings.demo or ctx.settings.router_pass:
        return []
    return [_finding(
        "router_pass_missing", "warn", "Router-Passwort fehlt",
        "Ohne Router-Zugangsdaten kann das Dashboard keine WANs auslesen, keine "
        "Schlüssel übertragen und keine Einstellungen am Router ändern. "
        "Anzeigen bleiben teilweise leer.",
        "Unter System → Verbindung das Router-Passwort hinterlegen und die "
        "Verbindung testen.",
        "/system", "connectivity")]


# --------------------------------------------------------------------------- #
# Connectivity
# --------------------------------------------------------------------------- #
def check_tunnel(ctx: AdvisorContext) -> list[Finding]:
    if ctx.status.state != BondState.offline:
        return []
    return [_finding(
        "tunnel_offline", "error", "Keine Verbindung",
        "Es ist aktuell kein Tunnel aktiv — der Verkehr läuft nicht über den VPS.",
        "Unter Diagnose prüfen, ob der VPS erreichbar ist; danach im "
        "Einrichtungs-Assistenten die Verbindung neu aufbauen.",
        "/diagnostics", "connectivity")]


def check_link_count(ctx: AdvisorContext) -> list[Finding]:
    enabled = [l for l in ctx.status.links if l.enabled]
    if len(enabled) >= 2:
        return []
    return [_finding(
        "single_link", "info", "Nur eine Leitung aktiv",
        "Bündelung braucht mindestens zwei Leitungen. Mit einer aktiven Leitung "
        "gibt es weder Mehrbandbreite noch Ausfallsicherheit.",
        "Unter Verbindungen eine weitere Leitung aktivieren — oder, falls eine "
        "fehlt, im Assistenten neu erkennen lassen.",
        "/links", "connectivity")]


def check_poor_links(ctx: AdvisorContext) -> list[Finding]:
    out: list[Finding] = []
    for link in ctx.status.links:
        if not link.enabled or link.state in (LinkState.disabled, LinkState.down):
            continue
        loss = link.packet_loss_pct or 0.0
        latency = link.latency_ms or 0.0
        if loss < POOR_LOSS_PCT and latency < POOR_LATENCY_MS:
            continue
        reasons = []
        if loss >= POOR_LOSS_PCT:
            reasons.append(f"{loss:.1f} % Paketverlust")
        if latency >= POOR_LATENCY_MS:
            reasons.append(f"{latency:.0f} ms Latenz")
        out.append(_finding(
            f"poor_link_{link.id}", "warn", f"{link.label} ist beeinträchtigt",
            f"Die Leitung meldet {' und '.join(reasons)}. Eine schlechte Leitung "
            "bremst die Bündelung aus, weil auf ihre Pakete gewartet wird.",
            "Wenn das dauerhaft so bleibt: unter Verbindungen die Leitung auf "
            "„backup“ stellen oder den Scheduler auf „blest“ setzen, der "
            "langsame Pfade automatisch weniger nutzt.",
            "/links", "connectivity"))
    return out


# --------------------------------------------------------------------------- #
# Data usage
# --------------------------------------------------------------------------- #
def _suggested_cap(link_type: LinkType) -> int:
    """A plausible starting cap in GB for a metered link type."""
    return {LinkType.lte: 100, LinkType.fiveg: 200, LinkType.satellite: 100}.get(link_type, 100)


def check_metered_without_cap(ctx: AdvisorContext) -> list[Finding]:
    out: list[Finding] = []
    for link in ctx.status.links:
        if not link.enabled or link.type not in METERED_TYPES:
            continue
        if (ctx.quotas.get(link.id) or {}).get("cap_gb"):
            continue
        suggested = _suggested_cap(link.type)
        out.append(_finding(
            f"no_cap_{link.id}", "warn", f"{link.label} ohne Datenlimit",
            "Mobilfunk- und Satellitenverträge sind fast immer volumenbegrenzt. "
            "Ohne hinterlegtes Limit warnt das Dashboard nicht, bevor der "
            "Vertrag gedrosselt wird.",
            f"Unter Datenverbrauch ein Monatslimit setzen — {suggested} GB ist "
            "ein üblicher Startwert, den Du an Deinen Tarif anpasst.",
            "/usage", "usage"))
    return out


def check_quota_status(ctx: AdvisorContext) -> list[Finding]:
    out: list[Finding] = []
    labels = {l.id: l.label for l in ctx.status.links}
    for link_id, quota in ctx.quotas.items():
        cap_gb = quota.get("cap_gb")
        if not cap_gb:
            continue
        rx, tx = ctx.usage.get(link_id, (0.0, 0.0))
        used_pct = (rx + tx) / (cap_gb * 1e9) * 100
        label = labels.get(link_id, link_id)
        if used_pct >= 100:
            out.append(_finding(
                f"cap_reached_{link_id}", "error", f"{label}: Datenlimit erreicht",
                f"{used_pct:.0f} % des Monatslimits von {cap_gb:g} GB sind verbraucht.",
                "Leitung unter Verbindungen auf „backup“ stellen, damit sie nur "
                "noch bei Ausfall genutzt wird.",
                "/usage", "usage"))
        elif used_pct >= (quota.get("warn_pct") or 80):
            out.append(_finding(
                f"cap_warn_{link_id}", "warn", f"{label}: Datenlimit fast erreicht",
                f"{used_pct:.0f} % des Monatslimits von {cap_gb:g} GB sind verbraucht.",
                "Verbrauch beobachten oder die Leitung vorübergehend "
                "zurückstufen.",
                "/usage", "usage"))
        elif ctx.month_progress > 0.15:
            # Only project once enough of the month has passed that the rate is
            # meaningful — on the 2nd of the month a single big download would
            # otherwise "predict" a massive overrun.
            projected_pct = used_pct / ctx.month_progress
            if projected_pct >= 100:
                out.append(_finding(
                    f"cap_forecast_{link_id}", "info",
                    f"{label}: Limit wird voraussichtlich überschritten",
                    f"Beim bisherigen Tempo sind zum Monatsende rund "
                    f"{projected_pct:.0f} % des Limits von {cap_gb:g} GB erreicht "
                    f"(aktuell {used_pct:.0f} %).",
                    "Jetzt gegensteuern ist einfacher als später: unter QoS "
                    "datenintensive Dienste auf eine andere Leitung routen.",
                    "/usage", "usage"))
    return out


# --------------------------------------------------------------------------- #
# Alerting
# --------------------------------------------------------------------------- #
def check_alert_channels(ctx: AdvisorContext) -> list[Finding]:
    enabled = any(ctx.alerts.get(k) for k in
                  ("telegram_enabled", "webhook_enabled", "email_enabled"))
    if enabled:
        return []
    return [_finding(
        "no_alert_channel", "info", "Keine Benachrichtigungen eingerichtet",
        "Ausfälle und erreichte Datenlimits landen nur im Ereignisprotokoll. "
        "Ohne Kanal erfährst Du davon erst, wenn Du selbst nachsiehst.",
        "Unter Alarme einen Kanal aktivieren — Telegram ist in zwei Minuten "
        "eingerichtet.",
        "/alerts", "alerting")]


def check_alert_cooldown(ctx: AdvisorContext) -> list[Finding]:
    if not any(ctx.alerts.get(k) for k in
               ("telegram_enabled", "webhook_enabled", "email_enabled")):
        return []
    if (ctx.alerts.get("cooldown_minutes") or 0) > 0:
        return []
    return [_finding(
        "no_cooldown", "info", "Wiederholsperre ist abgeschaltet",
        "Eine flatternde Leitung kann damit im Minutentakt Meldungen erzeugen.",
        "Unter Alarme eine Wiederholsperre von etwa 10 Minuten setzen.",
        "/alerts", "alerting")]


# --------------------------------------------------------------------------- #
# Protocol recommendation
# --------------------------------------------------------------------------- #
def recommend_protocol(links) -> tuple[str, str]:
    """Suggest a tunnel protocol from the mix of link types, with a reason.

    Mobile links vary in latency from second to second, which TCP-based tunnels
    handle badly (head-of-line blocking); UDP suits them. Stable wired links do
    best on the lowest-overhead option.
    """
    active = [l for l in links if l.enabled]
    if not active:
        return "glorytun_tcp", "Standardwahl, solange keine Leitungen erkannt sind."
    mobile = sum(1 for l in active if l.type in (LinkType.lte, LinkType.fiveg, LinkType.satellite))
    if mobile * 2 >= len(active):
        return ("glorytun_udp",
                "Mehrheitlich Mobilfunk-/Satellitenleitungen: UDP verkraftet "
                "schwankende Latenz deutlich besser als TCP.")
    return ("glorytun_tcp",
            "Überwiegend stabile Festnetzleitungen: geringster Overhead und "
            "bester Durchsatz.")


def check_protocol_choice(ctx: AdvisorContext) -> list[Finding]:
    tunnel = ctx.status.tunnel
    if tunnel is None or not ctx.status.links:
        return []
    best, reason = recommend_protocol(ctx.status.links)
    if tunnel.protocol == best:
        return []
    return [_finding(
        "protocol_suggestion", "info", "Ein anderes Protokoll passt besser",
        f"Aktiv ist {tunnel.protocol}. {reason}",
        f"Unter Protokoll auf {best} wechseln — der Tunnel wird dabei kurz neu "
        "aufgebaut. Wenn Dein Netz Deep Packet Inspection einsetzt, bleibt "
        "Shadowsocks die bessere Wahl.",
        "/protocols", "performance")]


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
CHECKS: list[Callable[[AdvisorContext], list[Finding]]] = [
    check_jwt_secret,
    check_dashboard_password,
    check_bind_address,
    check_router_credentials,
    check_tunnel,
    check_link_count,
    check_poor_links,
    check_metered_without_cap,
    check_quota_status,
    check_alert_channels,
    check_alert_cooldown,
    check_protocol_choice,
]

_SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}


def evaluate(ctx: AdvisorContext) -> list[Finding]:
    """Run every check, most severe first.

    A failing check never aborts the report: a broken individual check must not
    cost the user the other eleven answers.
    """
    findings: list[Finding] = []
    for check in CHECKS:
        try:
            findings.extend(check(ctx))
        except Exception:  # noqa: BLE001 — advisory output is best-effort
            continue
    findings.sort(key=lambda f: (_SEVERITY_ORDER.get(f.severity, 3), f.id))
    return findings


def bind_addr_from_env() -> str:
    return os.environ.get("BIND_ADDR", "127.0.0.1")
