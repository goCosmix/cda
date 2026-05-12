#!/usr/bin/env python3
"""
cda — Code Direct Ask
CLI for querying, searching, and managing the Code Data Ark session database.

Commands:
  cda search <query>         Full-text search across all exchanges
  cda code-search <pattern>  Search code symbols and content
  cda sessions               List all sessions (newest first)
  cda session <id>           Show all exchanges in a session
  cda exchange <id> <idx>    Show one full exchange with tool calls
  cda workspaces             List all registered workspaces
  cda workspace <id>         Show sessions for a workspace
  cda memory                 Show all memory files
  cda tools <query>          Search tool call arguments and names
  cda replay <id>            Print a session as a readable conversation
  cda stats                  System-wide stats and coverage summary
  cda status                 Watcher daemon status and queue information
  cda watch start            Start the live watcher daemon
  cda watch stop             Stop the watcher daemon
  cda watch restart          Restart the watcher daemon
  cda pmf services           List embedded PMF kernel services
  cda pmf start <service>    Start a service (ui, watcher, sync, etc.)
  cda pmf stop <service>     Stop a service
  cda pmf restart <service>  Restart a service
  cda pmf logs <service>     Tail service logs
  cda pmf up                 Start watcher + web UI (opens browser when ready)
  cda pmf install            Register as macOS LaunchAgent (auto-start on login)
  cda pmf uninstall          Remove the LaunchAgent registration
  cda check                  Run a full self-diagnostic. The system checks itself.
  cda init                   First-run setup — create ~/Library/goCosmix/ and validate environment
  cda setup                  Full onboarding: init → pmf install → sync → up (browser opens)
  cda serve                  Start the local web UI on port 10001
  cda sync                   Full re-ingest from disk (rebuilds entire DB)
  cda reconstruct            Re-run reconstruction and FTS rebuild only
  cda embed build            Build semantic embeddings and session intelligence
  cda query <sql>            Raw SQL query against the DB
  cda export <id>            Export a session as JSON, JSONL, or text
  cda vfs ls <session_id>    List VFS blobs for a session
  cda vfs cat <vfs_id>       Print decompressed content of a VFS blob
  cda policy allow <pattern> Add an allow pattern for search results
  cda policy deny <pattern>  Add a deny pattern for search results
  cda policy list            List current policies
  cda signals [session]      Show behavioral signals
  cda heat [session]         Frustration and heat analysis
  cda behavior               Aggregate behavioral intelligence
  cda saved                  Sessions that recovered from high heat
  cda tokens [session]       Token usage analysis
  cda compactions [session]  Context compaction events
  cda edits                  Edit session analytics
  cda semantic-search <query> Semantic search using embeddings
  cda similar <session>      Find sessions similar to a session
  cda summarize <session>    Show session summary, topics, and recommendations
  cda topics                 Show semantic topic tags
  cda alerts <session>       Show semantic anomaly alerts
  cda recommend <session>    Show session recommendations
"""

import os
import sys
import json
import gzip
import sqlite3
import subprocess
import textwrap
import datetime
from pathlib import Path
from cda.pipeline.reconstruct import decompress_vfs
from cda.kernel.pmf_kernel import (
    PMFKernel, PMFKernelError,
    install_launchd, uninstall_launchd, plist_path,
    open_browser_when_ready, wait_for_port_and_open_browser,
)
from cda.kernel.paths import (
    DB_PATH, PID_FILE, UI_PID_FILE, UI_LOG_FILE,
    QUEUE_DIR, POLICY_FILE, ensure_dirs,
)

import click

# Ensure runtime dirs exist on every CLI invocation
ensure_dirs()


def _pmf_warn_if_not_installed():
    """Emit a one-time advisory if the LaunchAgent is not registered."""
    if not plist_path().exists():
        click.echo(yellow("  Note: LaunchAgent not installed — services won't auto-start on login."))
        click.echo(yellow("        Run `cda setup` to register, or `cda pmf install` to add just the plist."))


kernel = PMFKernel()


# ─────────────────────────────────────────────
# ANSI colors (no dep)
# ─────────────────────────────────────────────

class C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[91m"
    GREEN  = "\033[92m"
    YELLOW = "\033[93m"
    BLUE   = "\033[94m"
    MAGENTA= "\033[95m"
    CYAN   = "\033[96m"
    WHITE  = "\033[97m"


def bold(s):    return f"{C.BOLD}{s}{C.RESET}"
def dim(s):     return f"{C.DIM}{s}{C.RESET}"
def green(s):   return f"{C.GREEN}{s}{C.RESET}"
def yellow(s):  return f"{C.YELLOW}{s}{C.RESET}"
def red(s):     return f"{C.RED}{s}{C.RESET}"
def cyan(s):    return f"{C.CYAN}{s}{C.RESET}"
def magenta(s): return f"{C.MAGENTA}{s}{C.RESET}"
def blue(s):    return f"{C.BLUE}{s}{C.RESET}"


def hr(char="─", width=80): return dim(char * width)


def fmt_ts(iso_or_ms):
    """Format ISO timestamp or ms-since-epoch to readable local time."""
    if not iso_or_ms:
        return dim("—")
    try:
        if isinstance(iso_or_ms, (int, float)):
            dt = datetime.datetime.fromtimestamp(iso_or_ms / 1000)
        else:
            dt = datetime.datetime.fromisoformat(str(iso_or_ms).replace("Z", "+00:00"))
            dt = dt.astimezone()
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(iso_or_ms)


def fmt_size(n):
    if n is None: return "—"
    if n < 1024: return f"{n}B"
    if n < 1024**2: return f"{n//1024}KB"
    return f"{n/1024/1024:.1f}MB"


def truncate(s, n=80):
    s = (s or "").replace("\n", " ").strip()
    return s[:n] + "…" if len(s) > n else s


def table(rows, headers, widths=None):
    """Print a simple aligned table."""
    if not rows:
        click.echo(dim("  (no results)"))
        return
    # Auto widths
    cols = len(headers)
    if widths is None:
        widths = [max(len(str(headers[i])), max(len(str(r[i])) for r in rows)) for i in range(cols)]
    header_line = "  " + "  ".join(bold(str(headers[i]).ljust(widths[i])) for i in range(cols))
    click.echo(header_line)
    click.echo("  " + dim("  ".join("─" * widths[i] for i in range(cols))))
    for row in rows:
        click.echo("  " + "  ".join(str(row[i]).ljust(widths[i]) for i in range(cols)))


# ─────────────────────────────────────────────
# DB
# ─────────────────────────────────────────────

def db():
    if not DB_PATH.exists():
        click.echo(red(f"DB not found: {DB_PATH}"))
        click.echo(f"Run: {bold('cda sync')} to initialize")
        sys.exit(1)
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def short_id(s, n=8):
    return (s or "")[:n]


def _decode_vfs_text(blob):
    if not blob:
        return ""
    try:
        raw = decompress_vfs(blob)
    except Exception:
        raw = blob
    if isinstance(raw, str):
        return raw
    for encoding in ('utf-8', 'latin-1'):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return ""


def _code_search_snippet(text, match, radius=80):
    start = max(0, match.start() - radius)
    end = min(len(text), match.end() + radius)
    snippet = text[start:end].replace("\n", " ")
    return snippet.strip()


def import_embed_module():
    try:
        import importlib
        import cda.embed as embed
        return importlib.reload(embed)
    except Exception as exc:
        raise RuntimeError(
            "Semantic intelligence requires the embed module and its dependencies. "
            "Install sentence-transformers and retry. "
            f"Details: {exc}"
        ) from exc


# ─────────────────────────────────────────────
# CLI root
# ─────────────────────────────────────────────

class CDAGroup(click.Group):
    def format_help(self, ctx, formatter):
        click.echo("================================================================================")
        click.echo("  CDA \u2014 Code Direct Ask")
        click.echo("================================================================================")
        click.echo("  System   : cda")
        click.echo(f"  Runtime  : {DB_PATH}")
        click.echo("  Status   : active\n")
        click.echo("Usage:")

        commands = []
        for cmd in self.list_commands(ctx):
            c = self.get_command(ctx, cmd)
            if c and not c.hidden:
                help_str = c.get_short_help_str(80) or ""
                commands.append((cmd, help_str))

        if commands:
            max_len = max(len(c[0]) for c in commands)
            for cmd, help_str in commands:
                click.echo(f"  cda {cmd.ljust(max_len)}    {help_str}")
        click.echo("")


@click.group(cls=CDAGroup, invoke_without_command=True)
@click.pass_context
@click.version_option(package_name="code-data-ark", prog_name="cda")
def cli(ctx):
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

@cli.command()
def stats():
    """System-wide stats and coverage summary."""
    conn = db()
    click.echo()
    click.echo(bold("  Code Data Ark  ") + dim(str(DB_PATH)))
    click.echo(hr())

    tables = [
        ("workspaces",         "Registered workspaces"),
        ("sessions",           "Total sessions"),
        ("exchanges",          "Reconstructed exchanges"),
        ("tool_calls",         "Indexed tool calls"),
        ("edit_sessions",      "Edit sessions parsed"),
        ("edited_files",       "Edited files tracked"),
        ("transcript_events",  "Transcript events"),
        ("chat_messages",      "Chat messages"),
        ("vfs",                "VFS blobs"),
        ("state_items",        "state.vscdb items"),
        ("memory_files",       "Memory files"),
        ("embeddings",         "Semantic embeddings"),
        ("session_summaries",  "Session summaries"),
        ("anomaly_alerts",     "Anomaly alerts"),
        ("recommendations",    "Recommendations"),
    ]
    for tbl, label in tables:
        try:
            n = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            click.echo(f"  {label:<30} {bold(str(n)):>10}")
        except Exception:
            pass

    click.echo()
    # VFS breakdown
    click.echo(bold("  VFS by type:"))
    for r in conn.execute("SELECT source_type, COUNT(*) n, SUM(size_bytes) total FROM vfs GROUP BY source_type ORDER BY total DESC").fetchall():
        click.echo(f"    {r['source_type']:<22} {r['n']:>6} files  {fmt_size(r['total']):>10} raw")

    click.echo()
    # Coverage
    has_t = conn.execute("SELECT COUNT(*) FROM session_storage WHERE has_transcript=1").fetchone()[0]
    has_c = conn.execute("SELECT COUNT(*) FROM session_storage WHERE has_chat_session=1").fetchone()[0]
    has_e = conn.execute("SELECT COUNT(*) FROM session_storage WHERE has_edit_session=1").fetchone()[0]
    has_to = conn.execute("SELECT COUNT(*) FROM session_storage WHERE has_tool_outputs=1").fetchone()[0]
    click.echo(bold("  Session coverage:"))
    click.echo(f"    Transcripts:      {has_t}")
    click.echo(f"    Chat sessions:    {has_c}")
    click.echo(f"    Edit sessions:    {has_e}")
    click.echo(f"    Tool outputs:     {has_to}")

    db_size = DB_PATH.stat().st_size
    click.echo()
    click.echo(f"  DB size: {bold(fmt_size(db_size))}")
    click.echo()
    conn.close()


# ─────────────────────────────────────────────
# STATUS (watcher)
# ─────────────────────────────────────────────

@cli.command()
def status():
    """Watcher daemon status."""
    print("STATUS COMMAND CALLED")
    click.echo()
    if PID_FILE.exists():
        pid = PID_FILE.read_text().strip()
        try:
            os.kill(int(pid), 0)
            click.echo(f"  Watcher: {green('RUNNING')}  pid={bold(pid)}")
        except (ProcessLookupError, ValueError):
            click.echo(f"  Watcher: {red('DEAD')}  (stale pid file: {pid})")
    else:
        click.echo(f"  Watcher: {yellow('STOPPED')}")
        click.echo(f"  Start with: {bold('cda watch start')}")

    # Queue status
    if QUEUE_DIR.exists():
        pending = len(list(QUEUE_DIR.glob("*.json")))
        completed = len(list(QUEUE_DIR.glob("*.completed")))
        click.echo(f"  Queue: {pending} pending, {completed} completed")
        if pending > 0:
            # Show last pending operation
            pending_files = sorted(QUEUE_DIR.glob("*.json"))
            if pending_files:
                try:
                    data = json.loads(pending_files[-1].read_text())
                    click.echo(f"  Last pending: {data.get('type', 'unknown')} at {fmt_ts(data.get('timestamp'))}")
                except Exception:
                    pass
    else:
        click.echo(f"  Queue: {dim('not initialized')}")

    # Last activity from file_offsets
    try:
        conn = db()
        row = conn.execute("SELECT MAX(updated_at) FROM file_offsets").fetchone()
        if row and row[0]:
            click.echo(f"  Last offset update: {fmt_ts(row[0])}")
        row2 = conn.execute("SELECT MAX(ingested_at) FROM transcript_events").fetchone()
        if row2 and row2[0]:
            click.echo(f"  Last event ingested: {fmt_ts(row2[0])}")
        conn.close()
    except Exception:
        pass
    click.echo()


@cli.command("backfill")
@click.option("--force", is_flag=True, default=False, help="Re-process all sessions, not just missing ones")
@click.option("--session", "session_id", default=None, metavar="SESSION_ID", help="Backfill a single session")
@click.option("--dry-run", is_flag=True, default=False, help="Show what would be processed without running")
@click.option("--symbols-only", is_flag=True, default=False, help="Only rebuild the symbol index")
def backfill(force, session_id, dry_run, symbols_only):
    """Backfill extract+embed pipeline for sessions missing analysis."""
    from cda.pipeline.backfill import run_backfill
    from cda.pipeline import extract
    conn = db()
    if symbols_only:
        extract.ensure_schema(conn)
        click.echo("Building symbol index...")
        extract.build_symbol_index(conn)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        click.echo(green(f"  {n} symbols indexed"))
        conn.close()
        return
    result = run_backfill(conn=conn, force=force, session_id=session_id, dry_run=dry_run)
    if result.get("errors", 0) > 0:
        raise SystemExit(1)


@cli.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Local host to bind the web UI")
@click.option("--port", default=10001, show_default=True, help="Local port for the web UI")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser automatically")
def serve(host, port, no_browser):
    """Start the local web UI for Code Data Ark in the foreground."""
    url = f"http://{host}:{port}"
    click.echo(yellow(f"  Starting local web UI at {url}"))
    try:
        import importlib
        import cda.ui.web as web
        importlib.reload(web)
    except Exception as exc:
        click.echo(red("  Failed to start web UI. Ensure the package is installed and importable."))
        click.echo(red(f"  Details: {exc}"))
        return
    if not no_browser:
        open_browser_when_ready(url, host, port)
    web.start_server(host=host, port=port)


@cli.group()
def ui():
    """Manage the Code Data Ark web UI as a background service."""
    pass


def _ui_is_running():
    if not UI_PID_FILE.exists():
        return False, None
    pid = UI_PID_FILE.read_text().strip()
    try:
        os.kill(int(pid), 0)
        return True, int(pid)
    except (ProcessLookupError, ValueError):
        return False, None


@ui.command("start")
@click.option("--host", default="127.0.0.1", show_default=True, help="Local host to bind the web UI")
@click.option("--port", default=10001, show_default=True, help="Local port for the web UI")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser automatically")
def ui_start(host, port, no_browser):
    """Start the web UI as a background service (via PMF kernel)."""
    _pmf_warn_if_not_installed()
    try:
        result = kernel.start_service("ui", options={"host": host, "port": port})
        url = f"http://{host}:{port}"
        click.echo(green(f"  Web UI started in background at {url} pid={result['pid']}"))
        click.echo(yellow(f"  Logs: {UI_LOG_FILE}"))
        if not no_browser:
            click.echo(dim("  Opening browser when server is ready..."))
            wait_for_port_and_open_browser(url, host, port)
    except PMFKernelError as exc:
        click.echo(red(f"  Failed to start UI: {exc}"))


@ui.command("stop")
def ui_stop():
    """Stop the background web UI service."""
    try:
        result = kernel.stop_service("ui")
        click.echo(green(f"  Stopped web UI pid={result['pid'] or 'unknown'}"))
    except PMFKernelError as exc:
        click.echo(yellow(f"  {exc}"))


@ui.command("status")
def ui_status():
    """Show whether the background web UI is running."""
    try:
        result = kernel.service_status("ui")
        if result["status"] == "running":
            click.echo(green(f"  Web UI is running pid={result['pid']}"))
            click.echo(f"  Log: {result['log_file']}")
        else:
            click.echo(yellow("  Web UI is not running."))
            click.echo("  Start it with: cda ui start")
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@ui.command("restart")
def ui_restart():
    """Restart the background web UI service."""
    try:
        kernel.restart_service("ui")
        click.echo(green("  Web UI restarted."))
    except PMFKernelError as exc:
        click.echo(red(f"  Failed to restart UI: {exc}"))


@cli.group()
def pmf():
    """Manage the embedded PMF kernel and Ark runtime services."""
    pass


@pmf.command("services")
def pmf_services():
    """List embedded PMF services and runtime status."""
    rows = kernel.services()
    click.echo()
    click.echo(bold("  EAK Runtime Services"))
    click.echo(hr())
    for service in rows:
        status = green(service["status"]) if service["status"] == "running" else yellow(service["status"])
        click.echo(f"  {bold(service['label']):<20} {status:<10} pid={service['pid'] or '—'}")
        click.echo(f"      {service['description']}")
    click.echo()


@pmf.command("status")
@click.argument("service_id", required=False)
def pmf_status(service_id):
    """Show PMF runtime status for one or all services."""
    if service_id:
        try:
            service = kernel.service_status(service_id)
            click.echo()
            click.echo(bold(f"  {service['label']}"))
            click.echo(f"  Status: {service['status']}")
            click.echo(f"  PID: {service['pid'] or '—'}")
            click.echo(f"  Started: {service['started_at'] or '—'}")
            click.echo(f"  Log: {service['log_file'] or '—'}")
            click.echo()
        except PMFKernelError as exc:
            click.echo(red(f"  {exc}"))
    else:
        pmf_services()


@pmf.command("start")
@click.argument("service_id")
@click.option("--host", default="127.0.0.1", help="Host override for UI service")
@click.option("--port", default=10001, help="Port override for UI service")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser (UI service only)")
def pmf_start(service_id, host, port, no_browser):
    """Start a PMF-managed Ark service."""
    options = {"host": host, "port": port} if service_id == "ui" else None
    try:
        result = kernel.start_service(service_id, options=options)
        click.echo(green(f"  Started {result['label']} pid={result['pid']}"))
        if service_id == "ui" and not no_browser:
            url = f"http://{host}:{port}"
            click.echo(dim("  Opening browser when server is ready..."))
            wait_for_port_and_open_browser(url, host, port)
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@pmf.command("stop")
@click.argument("service_id")
def pmf_stop(service_id):
    """Stop a PMF-managed Ark service."""
    try:
        result = kernel.stop_service(service_id)
        click.echo(green(f"  Stopped {result['label']}"))
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@pmf.command("restart")
@click.argument("service_id")
def pmf_restart(service_id):
    """Restart a PMF-managed Ark service."""
    try:
        result = kernel.restart_service(service_id)
        click.echo(green(f"  Restarted {result['label']} pid={result['pid']}"))
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@pmf.command("logs")
@click.argument("service_id")
@click.option("--tail", default=50, show_default=True, help="Lines to tail from the log file")
def pmf_logs(service_id, tail):
    """Display the last lines from a PMF service log."""
    try:
        output = kernel.tail_log(service_id, lines=tail)
        click.echo(output)
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@pmf.command("up")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host for web UI")
@click.option("--port", default=10001, show_default=True, help="Port for web UI")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser when UI is ready")
def pmf_up(host, port, no_browser):
    """Start all CDA services (watcher + web UI). Called automatically by launchd on login."""
    url = f"http://{host}:{port}"

    click.echo(bold("  Code Data Ark — starting services"))
    click.echo(hr())

    try:
        result = kernel.start_service("watcher")
        click.echo(green(f"  Watcher      started  pid={result['pid']}"))
    except PMFKernelError as exc:
        click.echo(yellow(f"  Watcher      {exc}"))

    try:
        result = kernel.start_service("ui", options={"host": host, "port": port})
        click.echo(green(f"  Web UI       started  pid={result['pid']}  →  {url}"))
        if not no_browser:
            click.echo(dim("  Opening browser when server is ready..."))
            wait_for_port_and_open_browser(url, host, port)
    except PMFKernelError as exc:
        click.echo(yellow(f"  Web UI       {exc}"))

    click.echo()


@pmf.command("install")
def pmf_install():
    """Install CDA as a macOS launchd LaunchAgent (auto-start on login)."""
    from cda.kernel.paths import CDA_HOME as _cda_home
    click.echo()
    click.echo(bold("  Installing CDA LaunchAgent"))
    click.echo(hr())
    try:
        target = install_launchd(_cda_home)
        click.echo(green(f"  Plist:   {target}"))
        click.echo(green("  Label:   com.gocosmix.cda"))
        click.echo(green("  Loaded:  yes — CDA will start automatically on next login"))
        click.echo()
        click.echo(dim("  To start services now without logging out:"))
        click.echo(dim("    cda eak up"))
        click.echo()
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))
        click.echo(yellow("  Make sure `cda` is on PATH: export PATH=\"$HOME/Library/Python/3.9/bin:$PATH\""))
        click.echo()


@pmf.command("uninstall")
def pmf_uninstall():
    """Remove the CDA launchd LaunchAgent."""
    target = plist_path()
    if not target.exists():
        click.echo(yellow("  No LaunchAgent plist found — nothing to uninstall."))
        return
    uninstall_launchd()
    click.echo(green(f"  Removed: {target}"))
    click.echo(green("  CDA will no longer start automatically on login."))


# ── EAK command group (Embedded App Kernel — canonical name for PMF) ─────────

@cli.group()
def eak():
    """Manage the Embedded App Kernel (EAK) and Ark runtime services."""
    pass


@eak.command("services")
@click.pass_context
def eak_services(ctx):
    """List EAK services and runtime status."""
    ctx.invoke(pmf_services)


@eak.command("status")
@click.argument("service_id", required=False)
@click.pass_context
def eak_status(ctx, service_id):
    """Show EAK runtime status for one or all services."""
    ctx.invoke(pmf_status, service_id=service_id)


@eak.command("start")
@click.argument("service_id")
@click.option("--host", default="127.0.0.1", help="Host override for UI service")
@click.option("--port", default=10001, help="Port override for UI service")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser (UI only)")
@click.pass_context
def eak_start(ctx, service_id, host, port, no_browser):
    """Start an EAK-managed Ark service or task."""
    ctx.invoke(pmf_start, service_id=service_id, host=host, port=port, no_browser=no_browser)


@eak.command("stop")
@click.argument("service_id")
@click.pass_context
def eak_stop(ctx, service_id):
    """Stop an EAK-managed Ark service."""
    ctx.invoke(pmf_stop, service_id=service_id)


@eak.command("restart")
@click.argument("service_id")
@click.pass_context
def eak_restart(ctx, service_id):
    """Restart an EAK-managed Ark service."""
    ctx.invoke(pmf_restart, service_id=service_id)


@eak.command("logs")
@click.argument("service_id")
@click.option("--tail", default=50, show_default=True, help="Lines to tail from the log file")
@click.pass_context
def eak_logs(ctx, service_id, tail):
    """Display the last lines from an EAK service log."""
    ctx.invoke(pmf_logs, service_id=service_id, tail=tail)


@eak.command("events")
@click.option("--tail", default=20, show_default=True, help="Number of recent kernel events to display")
def eak_events(tail):
    """Show recent EAK kernel events from the runtime event journal."""
    try:
        state = kernel._load_state()
        events = state.get("events", [])
        if not events:
            click.echo(dim("  No kernel events recorded yet."))
            return
        recent = events[-tail:]
        click.echo()
        click.echo(bold("  EAK Kernel Events"))
        click.echo(hr())
        for ev in reversed(recent):
            ts = ev.get("ts", "?")
            kind = ev.get("kind", "?")
            msg = ev.get("msg", "")
            click.echo(f"  {dim(ts)}  {bold(kind):<12}  {msg}")
        click.echo()
    except Exception as exc:
        click.echo(red(f"  Failed to read events: {exc}"))


@eak.command("check")
@click.option("--notify", is_flag=True, default=False, help="Fire macOS notifications for issues found")
def eak_check(notify):
    """Run health checks: watcher process, queue depth."""
    from cda.pipeline.alerting import run_health_check
    result = run_health_check(notify=notify)
    click.echo()
    click.echo(bold("  EAK Health Check"))
    click.echo(hr())
    w = result["watcher"]
    q = result["queue"]
    watcher_str = green(f"running  pid={w['pid']}") if w["healthy"] else red(f"DOWN  ({w.get('reason', '?')})")
    click.echo(f"  {'Watcher':<16} {watcher_str}")
    q_level = q["level"]
    q_str = f"{q['pending']} pending"
    q_colored = green(q_str) if q_level == "ok" else (yellow(q_str) if q_level == "warn" else red(q_str))
    click.echo(f"  {'Queue depth':<16} {q_colored}  ({q['completed']} completed)")
    if result["healthy"]:
        click.echo(green("  All systems healthy."))
    else:
        for issue in result["issues"]:
            click.echo(red(f"  ! {issue}"))
        if not notify:
            click.echo(dim("  Run with --notify to fire macOS notifications."))
    click.echo()


@eak.command("up")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host for web UI")
@click.option("--port", default=10001, show_default=True, help="Port for web UI")
@click.option("--no-browser", "no_browser", is_flag=True, default=False, help="Don't open browser when UI is ready")
@click.pass_context
def eak_up(ctx, host, port, no_browser):
    """Start all CDA services (watcher + web UI). Called automatically by launchd on login."""
    ctx.invoke(pmf_up, host=host, port=port, no_browser=no_browser)


@eak.command("down")
def eak_down():
    """Stop all CDA services (web UI + watcher)."""
    click.echo(bold("  Code Data Ark — stopping services"))
    click.echo(hr())
    for sid in ("ui", "watcher"):
        try:
            result = kernel.stop_service(sid)
            click.echo(green(f"  {result['label']:<12} stopped"))
        except PMFKernelError as exc:
            click.echo(yellow(f"  {sid:<12} {exc}"))
    click.echo()


@eak.command("install")
@click.pass_context
def eak_install(ctx):
    """Install CDA as a macOS launchd LaunchAgent (auto-start on login)."""
    ctx.invoke(pmf_install)


@eak.command("uninstall")
@click.pass_context
def eak_uninstall(ctx):
    """Remove the CDA launchd LaunchAgent."""
    ctx.invoke(pmf_uninstall)


# ── embed ──────────────────────────────────────────────────────────────────────

@cli.group()
def embed():
    """Build and inspect semantic intelligence."""
    pass


@embed.command("build")
def embed_build():
    """Build semantic embeddings and session intelligence."""
    click.echo(yellow("  Building semantic intelligence..."))
    result = subprocess.run([sys.executable, "-m", "cda.pipeline.embed"], capture_output=False)
    if result.returncode == 0:
        click.echo(green("  Embed build complete"))
    else:
        click.echo(red("  Embed build failed"))


@cli.command("semantic-search")
@click.argument("query")
@click.option("--limit", default=5, show_default=True, help="Maximum results")
def semantic_search(query, limit):
    """Semantic search using embeddings."""
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    results = embed.semantic_search(conn, query, top_k=limit)
    conn.close()
    if not results:
        click.echo(dim("  No semantic results found."))
        return
    click.echo(bold(f"  Top {len(results)} semantic matches:"))
    for idx, (row, score) in enumerate(results, 1):
        click.echo(f"  {idx}. [{row['entity_type']}] {row['entity_id'][:16]} score={score:.4f}")
        click.echo(f"      {truncate(row['content_text'], 140)}")


def _show_similar(session_id, limit):
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    results = embed.find_similar_entities(conn, "session", session_id, top_k=limit)
    conn.close()
    if not results:
        click.echo(dim("  No similar sessions found."))
        return
    click.echo(bold(f"  Similar sessions to {session_id[:16]}:"))
    for idx, (row, score) in enumerate(results, 1):
        click.echo(f"  {idx}. session={row['session_id'][:16]} agent={row['entity_type']} score={score:.4f}")
        click.echo(f"      {truncate(row['content_text'], 140)}")


@cli.command("similar")
@click.argument("session_id")
@click.option("--limit", default=5, show_default=True, help="Maximum similar sessions")
def similar(session_id, limit):
    """Find sessions similar to a given session."""
    _show_similar(session_id, limit)


@cli.command("related")
@click.argument("session_id")
@click.option("--limit", default=5, show_default=True, help="Maximum related sessions")
def related(session_id, limit):
    """Alias for finding sessions related by semantic similarity."""
    _show_similar(session_id, limit)


@cli.command("summarize")
@click.argument("session_id")
def summarize(session_id):
    """Show session summary, topic tags, and recommendations."""
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    summary = embed.get_session_summary(conn, session_id)
    alerts = embed.get_session_alerts(conn, session_id)
    recs = embed.get_session_recommendations(conn, session_id)
    conn.close()
    if not summary:
        click.echo(red("  No summary available. Run cda embed build first."))
        return
    click.echo(bold("  Summary:"))
    click.echo(f"    {summary['summary_text']}")
    click.echo(bold("  Topics:"))
    click.echo(f"    {summary['topic_tags'] or dim('none')}")
    if alerts:
        click.echo(bold("  Alerts:"))
        for a in alerts:
            click.echo(f"    [{a['severity']}] {a['message']}")
    if recs:
        click.echo(bold("  Recommendations:"))
        for r in recs:
            click.echo(f"    - {r['recommendation_text']}")


@cli.command("topics")
@click.option("--limit", default=20, show_default=True, help="Maximum topic tags to show")
def topics(limit):
    """Show semantic topic tags."""
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    topics = embed.get_topic_counts(conn, limit)
    conn.close()
    if not topics:
        click.echo(dim("  No topic tags available. Run cda embed build first."))
        return
    click.echo(bold("  Topic tags:"))
    for tag, count in topics:
        click.echo(f"    {tag:<18} {count}")


@cli.command("alerts")
@click.argument("session_id")
def alerts(session_id):
    """Show semantic anomaly alerts for a session."""
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    alerts = embed.get_session_alerts(conn, session_id)
    conn.close()
    if not alerts:
        click.echo(dim("  No alerts found."))
        return
    click.echo(bold("  Alerts:"))
    for a in alerts:
        click.echo(f"    [{a['severity']}] {a['message']}")


@cli.command("recommend")
@click.argument("session_id")
def recommend(session_id):
    """Show session recommendations."""
    try:
        embed = import_embed_module()
    except RuntimeError as exc:
        click.echo(red(str(exc)))
        return
    conn = db()
    recs = embed.get_session_recommendations(conn, session_id)
    conn.close()
    if not recs:
        click.echo(dim("  No recommendations found."))
        return
    click.echo(bold("  Recommendations:"))
    for r in recs:
        click.echo(f"    - {r['recommendation_text']}")


# ─────────────────────────────────────────────
# WATCH
# ─────────────────────────────────────────────

@cli.group()
def watch():
    """Manage the live watcher daemon."""
    pass


@watch.command("start")
def watch_start():
    """Start the live sync watcher daemon (via PMF kernel)."""
    _pmf_warn_if_not_installed()
    try:
        result = kernel.start_service("watcher")
        click.echo(green(f"  Watcher started  pid={result['pid']}  (via PMF)"))
    except PMFKernelError as exc:
        click.echo(red(f"  {exc}"))


@watch.command("stop")
def watch_stop():
    """Stop the live sync watcher daemon."""
    try:
        kernel.stop_service("watcher")
        click.echo(green("  Watcher stopped"))
    except PMFKernelError as exc:
        click.echo(yellow(f"  {exc}"))


@watch.command("restart")
def watch_restart():
    """Restart the watcher daemon."""
    try:
        result = kernel.restart_service("watcher")
        click.echo(green(f"  Watcher restarted pid={result['pid']}"))
    except PMFKernelError as exc:
        click.echo(red(f"  Failed to restart watcher: {exc}"))


# ─────────────────────────────────────────────
# SYNC / RECONSTRUCT
# ─────────────────────────────────────────────

@cli.command()
def sync():
    """Full re-ingest from disk (rebuilds entire DB)."""
    from cda.kernel.control_db import start_run, finish_run, log_event

    run_id = start_run(trigger="manual")
    stages_done = []
    errors = 0

    click.echo(yellow("  Running full ingest — this rewrites the DB..."))
    result = subprocess.run([sys.executable, "-m", "cda.pipeline.ingest"], capture_output=False)
    if result.returncode != 0:
        click.echo(red("  Ingest failed"))
        finish_run(run_id, stages_done, {}, errors=1, exit_code=1, notes="ingest failed")
        return
    stages_done.append("ingest")

    click.echo(green("  Ingest complete"))
    click.echo(yellow("  Running reconstruction..."))
    result = subprocess.run([sys.executable, "-m", "cda.pipeline.reconstruct"], capture_output=False)
    if result.returncode != 0:
        click.echo(red("  Reconstruction failed"))
        finish_run(run_id, stages_done, {}, errors=1, exit_code=1, notes="reconstruct failed")
        return
    stages_done.append("reconstruct")

    click.echo(green("  Reconstruction complete"))
    click.echo(yellow("  Running analysis..."))
    result = subprocess.run([sys.executable, "-m", "cda.pipeline.extract"], capture_output=False)
    if result.returncode != 0:
        click.echo(red("  Analysis failed"))
        finish_run(run_id, stages_done, {}, errors=1, exit_code=1, notes="extract failed")
        return
    stages_done.append("extract")

    click.echo(green("  Analysis complete"))
    click.echo(yellow("  Running semantic intelligence..."))
    result = subprocess.run([sys.executable, "-m", "cda.pipeline.embed"], capture_output=False)
    if result.returncode != 0:
        click.echo(red("  Semantic intelligence failed"))
        errors += 1
    else:
        stages_done.append("embed")

    # Collect final counts from cda.db
    counts = {}
    try:
        _conn = sqlite3.connect(DB_PATH)
        counts["sessions"]   = _conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        counts["exchanges"]  = _conn.execute("SELECT COUNT(*) FROM exchanges").fetchone()[0]
        counts["tool_calls"] = _conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        counts["vfs_files"]  = _conn.execute("SELECT COUNT(*) FROM vfs").fetchone()[0]
        _conn.close()
    except Exception:
        pass

    finish_run(run_id, stages_done, counts, errors=errors, exit_code=0)
    log_event("sync.complete", detail=f"sessions={counts.get('sessions')}, exchanges={counts.get('exchanges')}")
    click.echo(green("  Done"))


@cli.command()
def reconstruct():
    """Re-run session reconstruction and FTS rebuild only."""
    click.echo(yellow("  Reconstructing exchanges..."))
    subprocess.run([sys.executable, "-m", "cda.pipeline.reconstruct"], capture_output=False)
    click.echo(green("  Done"))


# ─────────────────────────────────────────────
# WORKSPACES
# ─────────────────────────────────────────────

@cli.command()
def workspaces():
    """List all registered workspaces."""
    conn = db()
    rows = conn.execute(
        "SELECT workspace_id, name, type, session_count, uri FROM workspaces ORDER BY session_count DESC"
    ).fetchall()
    conn.close()
    click.echo()
    click.echo(bold(f"  {len(rows)} workspaces"))
    click.echo(hr())
    for r in rows:
        sessions_label = green(str(r['session_count'])) if r['session_count'] > 0 else dim("0")
        click.echo(
            f"  {cyan(r['workspace_id'][:16])}  "
            f"{bold(truncate(r['name'] or '?', 30)):<32}  "
            f"{dim(r['type'] or '?'):<10}  "
            f"{sessions_label} sessions"
        )
        click.echo(f"             {dim(truncate(r['uri'] or '', 70))}")
    click.echo()


@cli.command()
@click.argument("workspace_id")
def workspace(workspace_id):
    """Show all sessions for a workspace (partial ID ok)."""
    conn = db()
    rows = conn.execute(
        """SELECT s.session_id, s.title, s.created_at, s.last_message_at,
                  s.request_count, ss.has_transcript, ss.has_chat_session, ss.has_tool_outputs
           FROM sessions s
           LEFT JOIN session_storage ss USING(session_id)
           WHERE s.workspace_id LIKE ?
           ORDER BY s.last_message_at DESC""",
        (f"{workspace_id}%",)
    ).fetchall()
    conn.close()
    click.echo()
    click.echo(bold(f"  {len(rows)} sessions in workspace {cyan(workspace_id[:16])}"))
    click.echo(hr())
    for r in rows:
        flags = ""
        if r['has_transcript']: flags += green("T")
        if r['has_chat_session']: flags += cyan("C")
        if r['has_tool_outputs']: flags += yellow("O")
        click.echo(
            f"  {cyan(r['session_id'][:16])}  "
            f"{bold(truncate(r['title'] or 'untitled', 42)):<44}  "
            f"{fmt_ts(r['last_message_at'])}  "
            f"{dim(str(r['request_count'] or 0)+' evts')}"
            f"  [{flags}]"
        )
    click.echo()


# ─────────────────────────────────────────────
# SESSIONS
# ─────────────────────────────────────────────

@cli.command()
@click.option("--workspace", "-w", default=None, help="Filter by workspace ID prefix")
@click.option("--limit", "-n", default=50, help="Max results")
def sessions(workspace, limit):
    """List sessions, newest first."""
    conn = db()
    if workspace:
        rows = conn.execute(
            """SELECT s.session_id, s.workspace_id, s.title, s.created_at, s.last_message_at, s.request_count
               FROM sessions s WHERE s.workspace_id LIKE ?
               ORDER BY s.last_message_at DESC LIMIT ?""",
            (f"{workspace}%", limit)
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT s.session_id, s.workspace_id, s.title, s.created_at, s.last_message_at, s.request_count
               FROM sessions s ORDER BY s.last_message_at DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    conn.close()
    click.echo()
    click.echo(bold(f"  {len(rows)} sessions"))
    click.echo(hr())
    for r in rows:
        click.echo(
            f"  {cyan(r['session_id'][:16])}  "
            f"{dim(r['workspace_id'][:8])}  "
            f"{bold(truncate(r['title'] or 'untitled', 44)):<46}  "
            f"{fmt_ts(r['last_message_at'])}"
        )
    click.echo()


# ─────────────────────────────────────────────
# SESSION (detail)
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id")
def session(session_id):
    """Show all exchanges in a session."""
    conn = db()
    meta = conn.execute(
        "SELECT * FROM sessions WHERE session_id LIKE ?", (f"{session_id}%",)
    ).fetchone()
    if not meta:
        click.echo(red(f"  Session not found: {session_id}"))
        conn.close()
        return

    sid = meta['session_id']
    click.echo()
    click.echo(bold(f"  Session: {cyan(sid[:16])}"))
    click.echo(f"  Title:   {bold(meta['title'] or 'untitled')}")
    click.echo(f"  Created: {fmt_ts(meta['created_at'])}  Last msg: {fmt_ts(meta['last_message_at'])}")
    click.echo(hr())

    rows = conn.execute(
        """SELECT exchange_index, user_ts, user_message, reasoning_text, response_text,
                  tool_call_count, has_tool_output
           FROM exchanges WHERE session_id=? ORDER BY exchange_index""",
        (sid,)
    ).fetchall()
    conn.close()

    for r in rows:
        tc = r['tool_call_count'] or 0
        has_out = r['has_tool_output']
        tc_label = (green if has_out else yellow)(f" [{tc} tools]") if tc > 0 else ""
        r_len = len(r['reasoning_text'] or "")
        resp_len = len(r['response_text'] or "")
        idx_str = bold(f"[{r['exchange_index']:>2}]")
        dim_str = dim(f"reason:{r_len}b resp:{resp_len}b")
        click.echo(
            f"  {idx_str}  "
            f"{fmt_ts(r['user_ts'])}  "
            f"{tc_label}  "
            f"{dim_str}"
        )
        msg = truncate(r['user_message'] or "", 80)
        if msg:
            click.echo(f"        {cyan('>')} {msg}")
    click.echo()
    click.echo(dim(f"  Use: cda exchange {sid[:16]} <index>  to view full exchange"))
    click.echo()


# ─────────────────────────────────────────────
# EXCHANGE (full detail)
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id")
@click.argument("index", type=int)
@click.option("--tool-outputs", "-t", is_flag=True, help="Include full tool output content")
@click.option("--reasoning", "-r", is_flag=True, help="Include reasoning text")
def exchange(session_id, index, tool_outputs, reasoning):
    """Show one full exchange with all tool calls."""
    conn = db()
    row = conn.execute(
        """SELECT * FROM exchanges WHERE session_id LIKE ? AND exchange_index=?""",
        (f"{session_id}%", index)
    ).fetchone()
    if not row:
        click.echo(red(f"  Exchange [{index}] not found in session {session_id}"))
        conn.close()
        return

    click.echo()
    click.echo(bold(f"  Exchange [{index}]  —  {cyan(row['session_id'][:16])}"))
    click.echo(f"  {fmt_ts(row['user_ts'])}")
    click.echo(hr())

    # User message
    click.echo(bold(f"\n  {cyan('USER')}"))
    for line in (row['user_message'] or "").splitlines():
        click.echo(f"    {line}")

    # Reasoning
    if reasoning and row['reasoning_text']:
        click.echo(bold(f"\n  {magenta('REASONING')}"))
        for line in textwrap.wrap(row['reasoning_text'], 90):
            click.echo(f"    {dim(line)}")

    # Tool calls
    if row['tool_call_count']:
        click.echo(bold(f"\n  {yellow('TOOL CALLS')}  ({row['tool_call_count']})"))
        try:
            calls = json.loads(row['tool_calls'] or "[]")
        except Exception:
            calls = []
        for i, tc in enumerate(calls):
            click.echo(f"\n    {bold(f'[{i}]')} {yellow(tc.get('name', '?'))}  {dim(tc.get('toolCallId', '')[:24])}")
            args = tc.get('arguments', {})
            if isinstance(args, dict):
                for k, v in args.items():
                    v_str = truncate(str(v), 100)
                    click.echo(f"        {cyan(k)}: {v_str}")
            elif args:
                click.echo(f"        {truncate(str(args), 100)}")
            success = tc.get('success')
            if success is not None:
                label = green("✓") if success else red("✗")
                click.echo(f"        {label} success={success}")
            if tool_outputs and tc.get('output'):
                click.echo(f"        {bold('output:')}")
                for line in (tc['output'] or "")[:2000].splitlines():
                    click.echo(f"          {dim(line)}")

    # Response
    if row['response_text']:
        click.echo(bold(f"\n  {green('ASSISTANT')}"))
        for line in (row['response_text'] or "").splitlines():
            click.echo(f"    {line}")

    click.echo()
    conn.close()


# ─────────────────────────────────────────────
# REPLAY
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id")
@click.option("--reasoning", "-r", is_flag=True, help="Include reasoning text")
def replay(session_id, reasoning):
    """Print a full session as a readable conversation."""
    conn = db()
    meta = conn.execute(
        "SELECT * FROM sessions WHERE session_id LIKE ?", (f"{session_id}%",)
    ).fetchone()
    if not meta:
        click.echo(red(f"  Session not found: {session_id}"))
        conn.close()
        return

    sid = meta['session_id']
    rows = conn.execute(
        "SELECT * FROM exchanges WHERE session_id=? ORDER BY exchange_index",
        (sid,)
    ).fetchall()
    conn.close()

    click.echo()
    click.echo(bold(f"  ═══ {meta['title'] or 'Session'} ═══"))
    click.echo(dim(f"  {sid}  ·  {fmt_ts(meta['created_at'])}"))
    click.echo()

    for r in rows:
        if r['user_message']:
            click.echo(f"{cyan(bold('  YOU'))}  {dim(fmt_ts(r['user_ts']))}")
            click.echo()
            for line in (r['user_message'] or "").splitlines():
                click.echo(f"    {line}")
            click.echo()

        if reasoning and r['reasoning_text']:
            click.echo(f"{magenta(bold('  [thinking]'))}")
            for line in textwrap.wrap(r['reasoning_text'][:500], 88):
                click.echo(f"    {dim(line)}")
            click.echo()

        if r['tool_call_count']:
            try:
                calls = json.loads(r['tool_calls'] or "[]")
            except Exception:
                calls = []
            names = ", ".join(tc.get('name', '?') for tc in calls[:5])
            more = f" +{len(calls)-5}" if len(calls) > 5 else ""
            click.echo(f"  {yellow(bold('  ⚙'))}  {dim(f'tools: {names}{more}')}")
            click.echo()

        if r['response_text']:
            click.echo(f"{green(bold('  CDA'))}")
            click.echo()
            for line in (r['response_text'] or "").splitlines():
                click.echo(f"    {line}")
            click.echo()

        click.echo(dim(f"  {'─' * 76}"))
        click.echo()


# ─────────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────────

@cli.command()
@click.argument("query")
@click.option("--session", "-s", default=None, help="Limit to session ID prefix")
@click.option("--workspace", "-w", default=None, help="Limit to workspace ID prefix")
@click.option("--limit", "-n", default=20, help="Max results")
@click.option("--full", "-f", is_flag=True, help="Show full response text, not snippet")
def search(query, session, workspace, limit, full):
    """Full-text search across all exchanges."""
    conn = db()
    # Quote hyphens for FTS5
    fts_query = f'"{query}"' if '-' in query and not query.startswith('"') else query
    hl_open  = "\033[93m"
    hl_close = "\033[0m"
    try:
        sql = (
            "SELECT e.session_id, e.workspace_id, e.exchange_index, e.user_ts,"
            " e.user_message, e.response_text, e.tool_call_count,"
            f" snippet(fts_exchanges, 4, '{hl_open}', '{hl_close}', '...', 20) AS snip"
            " FROM fts_exchanges"
            " JOIN exchanges e ON e.id = fts_exchanges.rowid"
            " WHERE fts_exchanges MATCH ?"
        )
        params = [fts_query]
        if session:
            sql += " AND e.session_id LIKE ?"
            params.append(f"{session}%")
        if workspace:
            sql += " AND e.workspace_id LIKE ?"
            params.append(f"{workspace}%")
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        click.echo(red(f"  Search error: {e}"))
        conn.close()
        return

    conn.close()
    click.echo()
    click.echo(bold(f"  {len(rows)} results for {cyan(repr(query))}"))
    click.echo(hr())

    filtered_rows = []
    for r in rows:
        # Apply policy filter
        text_to_check = (r['user_message'] or '') + ' ' + (r['response_text'] or '')
        if check_policy(text_to_check):
            filtered_rows.append(r)

    if len(filtered_rows) != len(rows):
        click.echo(yellow(f"  Policy filtered: {len(rows) - len(filtered_rows)} results hidden"))
        click.echo()

    for r in filtered_rows:
        tc_label = yellow(f"[{r['tool_call_count']} tools] ") if r['tool_call_count'] else ""
        idx_str = bold(f"[{r['exchange_index']:>2}]")
        click.echo(
            f"\n  {cyan(r['session_id'][:16])}  "
            f"{dim(r['workspace_id'][:8])}  "
            f"{idx_str}  "
            f"{fmt_ts(r['user_ts'])}  {tc_label}"
        )
        if r['user_message']:
            click.echo(f"  {cyan('Q:')} {truncate(r['user_message'], 80)}")
        if full and r['response_text']:
            click.echo(f"  {green('A:')} {truncate(r['response_text'], 120)}")
        else:
            click.echo(f"  {dim(r['snip'])}")
        click.echo(f"  {dim('cda exchange ' + r['session_id'][:16] + ' ' + str(r['exchange_index']))}")

    click.echo()


# ─────────────────────────────────────────────
# TOOLS SEARCH
# ─────────────────────────────────────────────

@cli.command()
@click.argument("query", default="")
@click.option("--limit", "-n", default=30)
@click.option("--top", is_flag=True, help="Show top tools by call count")
def tools(query, limit, top):
    """Search tool calls table. No query = show top tools by frequency."""
    conn = db()
    click.echo()

    if top or not query:
        rows = conn.execute(
            """SELECT tool_name, COUNT(*) n, COUNT(DISTINCT session_id) sessions,
               SUM(has_output) with_output
               FROM tool_calls GROUP BY tool_name ORDER BY n DESC LIMIT ?""",
            (limit,)
        ).fetchall()
        conn.close()
        click.echo(bold(f"  Tool call frequency (top {len(rows)})"))
        click.echo(hr())
        for r in rows:
            click.echo(
                f"  {yellow(r['tool_name']):<45}  "
                f"{bold(str(r['n'])):>6} calls  "
                f"{r['sessions']:>4} sessions  "
                f"{dim(str(r['with_output'])+' w/output')}"
            )
        click.echo()
        return

    q = f'%{query}%'
    rows = conn.execute(
        """SELECT session_id, exchange_index, tool_name, file_path, arguments_json, has_output
           FROM tool_calls
           WHERE tool_name LIKE ? OR file_path LIKE ? OR arguments_json LIKE ?
           ORDER BY session_id, exchange_index LIMIT ?""",
        (q, q, q, limit)
    ).fetchall()
    conn.close()

    click.echo(bold(f"  {len(rows)} tool calls matching {cyan(repr(query))}"))
    click.echo(hr())
    for r in rows:
        fp = dim(f"  → {r['file_path']}") if r['file_path'] else ''
        out = green(" [out]") if r['has_output'] else ''
        click.echo(
            f"  {dim(r['session_id'][:16])}  [{r['exchange_index']:>2}]  "
            f"{yellow(r['tool_name'])}{out}{fp}"
        )
    click.echo()


# ─────────────────────────────────────────────
# EDITS
# ─────────────────────────────────────────────

@cli.command()
@click.option("--session", "-s", default=None, help="Show edits for a specific session")
@click.option("--file", "-f", "file_query", default=None, help="Filter by file path substring")
@click.option("--changed-only", is_flag=True, help="Show only sessions with modifications")
@click.option("--limit", "-n", default=30)
def edits(session, file_query, changed_only, limit):
    """Show edit session analytics (files modified per session)."""
    conn = db()
    click.echo()

    if session:
        # Detail view for one session
        row = conn.execute(
            "SELECT * FROM edit_sessions WHERE session_id=?", (session,)
        ).fetchone()
        if not row:
            click.echo(red(f"  No edit session for: {session}"))
            conn.close()
            return
        click.echo(bold(f"  Edit session: {cyan(session[:16])}"))
        click.echo(hr())
        click.echo(f"  Total files:    {row['total_files']}")
        click.echo(f"  Modified files: {bold(str(row['modified_files']))}")
        click.echo(f"  Edit rounds:    {row['edit_rounds']}")
        click.echo()
        files = conn.execute(
            "SELECT file_path, language_id, was_modified FROM edited_files WHERE session_id=? ORDER BY was_modified DESC, file_path",
            (session,)
        ).fetchall()
        for f in files:
            marker = green("  ✓ ") if f['was_modified'] else dim("  · ")
            click.echo(f"{marker}{f['file_path']}  {dim(f['language_id'] or '')}")
        click.echo()
        conn.close()
        return

    if file_query:
        rows = conn.execute(
            """SELECT ef.session_id, ef.file_path, ef.language_id, ef.was_modified
               FROM edited_files ef WHERE ef.file_path LIKE ?
               ORDER BY ef.was_modified DESC, ef.file_path LIMIT ?""",
            (f'%{file_query}%', limit)
        ).fetchall()
        conn.close()
        click.echo(bold(f"  {len(rows)} file records matching {cyan(repr(file_query))}"))
        click.echo(hr())
        for r in rows:
            marker = green("  ✓ ") if r['was_modified'] else dim("  · ")
            click.echo(f"{marker}{dim(r['session_id'][:16])}  {r['file_path']}  {dim(r['language_id'] or '')}")
        click.echo()
        return

    # Summary view
    sql = "SELECT session_id, total_files, modified_files, edit_rounds FROM edit_sessions"
    if changed_only:
        sql += " WHERE modified_files > 0"
    sql += " ORDER BY modified_files DESC, total_files DESC LIMIT ?"
    rows = conn.execute(sql, (limit,)).fetchall()

    total_mod = conn.execute("SELECT SUM(modified_files) FROM edit_sessions").fetchone()[0] or 0
    total_sess = conn.execute("SELECT COUNT(*) FROM edit_sessions").fetchone()[0]
    with_changes = conn.execute("SELECT COUNT(*) FROM edit_sessions WHERE modified_files>0").fetchone()[0]
    conn.close()

    click.echo(bold(f"  {total_sess} edit sessions  |  {with_changes} with changes  |  {total_mod} total modified files"))
    click.echo(hr())
    for r in rows:
        mod_label = bold(green(str(r['modified_files']))) if r['modified_files'] else dim("0")
        click.echo(
            f"  {cyan(r['session_id'][:16])}  "
            f"files={r['total_files']:>4}  "
            f"modified={mod_label}  "
            f"rounds={dim(str(r['edit_rounds']))}"
        )
    click.echo()


# ─────────────────────────────────────────────
# MEMORY
# ─────────────────────────────────────────────

@cli.command()
@click.option("--scope", default=None, help="Filter: global | workspace | session | repo")
@click.option("--cat", default=None, help="Print content of file by filename")
def memory(scope, cat):
    """Show all memory files (global + workspace)."""
    conn = db()

    if cat:
        row = conn.execute(
            "SELECT scope, workspace_id, filename, content FROM memory_files WHERE filename LIKE ?",
            (f"%{cat}%",)
        ).fetchone()
        conn.close()
        if not row:
            click.echo(red(f"  No memory file matching: {cat}"))
            return
        click.echo()
        click.echo(bold(f"  [{row['scope']}] {row['filename']}  {dim(row['workspace_id'] or '')}"))
        click.echo(hr())
        click.echo(row['content'])
        return

    sql = "SELECT scope, workspace_id, filename, size_bytes, ingested_at FROM memory_files"
    params = []
    if scope:
        sql += " WHERE scope=?"
        params.append(scope)
    sql += " ORDER BY scope, filename"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    click.echo()
    click.echo(bold(f"  {len(rows)} memory files"))
    click.echo(hr())
    for r in rows:
        scope_label = cyan(r['scope']) if r['scope'] == 'global' else green(r['scope'])
        click.echo(
            f"  [{scope_label}]  "
            f"{bold(r['filename']):<40}  "
            f"{fmt_size(r['size_bytes']):>8}  "
            f"{dim(r['workspace_id'] or '(global)')}"
        )
    click.echo()


# ─────────────────────────────────────────────
# VFS
# ─────────────────────────────────────────────

@cli.group()
def vfs():
    """VFS blob storage operations."""
    pass


@vfs.command("ls")
@click.argument("session_id")
def vfs_ls(session_id):
    """List VFS blobs for a session."""
    conn = db()
    rows = conn.execute(
        """SELECT id, source_type, filename, size_bytes, sha256, ingested_at
           FROM vfs WHERE session_id LIKE ? ORDER BY source_type, filename""",
        (f"{session_id}%",)
    ).fetchall()
    conn.close()
    click.echo()
    click.echo(bold(f"  {len(rows)} VFS blobs for {cyan(session_id[:16])}"))
    click.echo(hr())
    for r in rows:
        click.echo(
            f"  {bold(str(r['id'])):>8}  "
            f"{yellow(r['source_type']):<18}  "
            f"{r['filename']:<35}  "
            f"{fmt_size(r['size_bytes']):>10}  "
            f"{dim(r['sha256'])}"
        )
    click.echo()


@vfs.command("cat")
@click.argument("vfs_id", type=int)
@click.option("--raw", "-r", is_flag=True, help="Print raw bytes (hex)")
@click.option("--lines", "-n", default=0, type=int, help="Limit output lines")
def vfs_cat(vfs_id, raw, lines):
    """Print decompressed content of a VFS blob."""
    conn = db()
    row = conn.execute(
        "SELECT source_type, filename, content, size_bytes FROM vfs WHERE id=?", (vfs_id,)
    ).fetchone()
    conn.close()
    if not row:
        click.echo(red(f"  VFS blob {vfs_id} not found"))
        return
    try:
        data = gzip.decompress(row['content'])
    except Exception:
        data = row['content']

    click.echo()
    click.echo(bold(f"  VFS {vfs_id}  {yellow(row['source_type'])}  {row['filename']}  {fmt_size(row['size_bytes'])}"))
    click.echo(hr())

    if raw:
        click.echo(data.hex())
        return

    text = data.decode('utf-8', errors='replace')
    if lines > 0:
        output_lines = text.splitlines()[:lines]
        text = "\n".join(output_lines)
    click.echo(text)


@vfs.command("types")
def vfs_types():
    """Summary of VFS blob types and sizes."""
    conn = db()
    rows = conn.execute(
        "SELECT source_type, COUNT(*) n, SUM(size_bytes) total, SUM(LENGTH(content)) compressed FROM vfs GROUP BY source_type ORDER BY total DESC"
    ).fetchall()
    conn.close()
    click.echo()
    click.echo(bold("  VFS storage summary"))
    click.echo(hr())
    for r in rows:
        ratio = (r['compressed'] / r['total'] * 100) if r['total'] else 0
        click.echo(
            f"  {yellow(r['source_type']):<22}  "
            f"{r['n']:>6} blobs  "
            f"{fmt_size(r['total']):>10} raw  "
            f"{fmt_size(r['compressed']):>10} stored  "
            f"{dim(f'{ratio:.0f}% ratio')}"
        )
    click.echo()


# ─────────────────────────────────────────────
# POLICY
# ─────────────────────────────────────────────

@cli.group()
def policy():
    """Manage data access policies."""
    pass


@policy.command("allow")
@click.argument("pattern")
def policy_allow(pattern):
    """Add an allow pattern for search results."""
    # For now, store in a simple text file
    try:
        with open(POLICY_FILE, "a") as f:
            f.write(f"ALLOW {pattern}\n")
        click.echo(green(f"  Added allow pattern: {pattern}"))
    except Exception as e:
        click.echo(red(f"  Error: {e}"))


@policy.command("deny")
@click.argument("pattern")
def policy_deny(pattern):
    """Add a deny pattern for search results."""
    try:
        with open(POLICY_FILE, "a") as f:
            f.write(f"DENY {pattern}\n")
        click.echo(green(f"  Added deny pattern: {pattern}"))
    except Exception as e:
        click.echo(red(f"  Error: {e}"))


@policy.command("list")
def policy_list():
    """List current policies."""
    if not POLICY_FILE.exists():
        click.echo(dim("  No policies configured"))
        return

    click.echo()
    click.echo(bold("  Data Access Policies"))
    click.echo(hr())
    try:
        with open(POLICY_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ALLOW "):
                    click.echo(green(f"  ALLOW {line[6:]}"))
                elif line.startswith("DENY "):
                    click.echo(red(f"  DENY {line[5:]}"))
    except Exception as e:
        click.echo(red(f"  Error reading policies: {e}"))
    click.echo()


def check_policy(text):
    """Check if text passes policy filters. Returns True if allowed."""
    if not POLICY_FILE.exists():
        return True  # No policies = allow all

    allow_patterns = []
    deny_patterns = []
    try:
        with open(POLICY_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line.startswith("ALLOW "):
                    allow_patterns.append(line[6:])
                elif line.startswith("DENY "):
                    deny_patterns.append(line[5:])

        # Check deny patterns first - if any match, deny
        for deny in deny_patterns:
            if deny in text:
                return False

        # If no allow patterns, allow (since deny check passed)
        if not allow_patterns:
            return True

        # If allow patterns exist, check if any match
        for allow in allow_patterns:
            if allow in text:
                return True

        # Allow patterns exist but none match - deny
        return False

    except Exception:
        return True  # On error, allow


# ─────────────────────────────────────────────
@cli.command()
@click.argument("pattern")
@click.option("--symbol", "-s", is_flag=True, help="Search symbols only")
@click.option("--path", "-p", type=str, help="Filter by file path pattern")
@click.option("--regex", "-r", is_flag=True, help="Treat pattern as regex")
@click.option("--workspace", "-w", type=str, help="Filter by workspace ID")
@click.option("--limit", "-l", type=int, default=50, help="Max results")
def code_search(pattern, symbol, path, regex, workspace, limit):
    """Search code symbols and content using AST-indexed data."""
    conn = db()

    # If symbol search, use symbols table
    if symbol:
        try:
            query = "SELECT file_path, symbol_name, symbol_type, line_number, context FROM symbols WHERE 1=1"
            params = []

            if workspace:
                query += " AND workspace_id LIKE ?"
                params.append(f"{workspace}%")

            if regex:
                # For regex, we'd need more complex logic - for now, use LIKE
                query += " AND symbol_name LIKE ?"
                params.append(f"%{pattern}%")
            else:
                query += " AND symbol_name LIKE ?"
                params.append(f"%{pattern}%")

            if path:
                query += " AND file_path LIKE ?"
                params.append(f"%{path}%")

            query += f" ORDER BY symbol_name LIMIT {limit}"

            rows = conn.execute(query, params).fetchall()
        except sqlite3.OperationalError as e:
            if "no such table" in str(e):
                click.echo(yellow("  Symbols table not yet created. Run 'python extract.py' to initialize."))
                conn.close()
                return
            raise
        conn.close()

        if not rows:
            click.echo(dim(f"  No symbols found matching '{pattern}'"))
            return

        click.echo()
        click.echo(bold(f"  Code symbols ({len(rows)} results)"))
        click.echo(hr())
        for r in rows:
            click.echo(f"  {cyan(r['symbol_type']):<10} {bold(r['symbol_name']):<30} {dim(r['file_path'])}:{r['line_number']}")
            if r['context']:
                click.echo(f"    {dim(truncate(r['context'], 100))}")
        click.echo()

    else:
        import re

        query = "SELECT workspace_id, source_path, source_type, content_type, content, size_bytes FROM vfs WHERE source_type IN ('edit_content','edit_state','memory_workspace','memory_global')"  # noqa: E501
        params = []
        if workspace:
            query += " AND workspace_id LIKE ?"
            params.append(f"{workspace}%")
        if path:
            query += " AND source_path LIKE ?"
            params.append(f"%{path}%")

        rows = conn.execute(query, params).fetchall()
        results = []
        lower_pattern = pattern.lower() if not regex else None
        compiled = None
        if regex:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
            except re.error:
                click.echo(red("  Invalid regex pattern."))
                conn.close()
                return

        for workspace_id, source_path, source_type, content_type, content_blob, size_bytes in rows:
            text = _decode_vfs_text(content_blob)
            if not text:
                continue
            if regex:
                m = compiled.search(text)
                if not m:
                    continue
                snippet = _code_search_snippet(text, m)
            else:
                if lower_pattern not in text.lower():
                    continue
                idx = text.lower().find(lower_pattern)
                m = re.search(re.escape(pattern), text[idx:idx+len(pattern)+1]) if idx >= 0 else None
                start = max(0, idx - 80)
                end = min(len(text), idx + len(pattern) + 80)
                snippet = text[start:end].replace("\n", " ").strip()

            results.append((workspace_id, source_path, source_type, snippet))
            if len(results) >= limit:
                break

        conn.close()

        if not results:
            click.echo(dim(f"  No code content found matching '{pattern}'"))
            return

        click.echo()
        click.echo(bold(f"  Code content results ({len(results)} results)"))
        click.echo(hr())
        for workspace_id, source_path, source_type, snippet in results:
            click.echo(f"  {bold(source_path)} {dim(source_type)} {dim(short_id(workspace_id, 10))}")
            click.echo(f"    {dim(truncate(snippet, 180))}")
        click.echo()


# ─────────────────────────────────────────────
# EXPORT
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id")
@click.option("--output", "-o", default=None, help="Output file path (default: stdout)")
@click.option("--format", "-f", "fmt", type=click.Choice(["json", "jsonl", "text"]), default="json")
def export(session_id, output, fmt):
    """Export a session as JSON, JSONL, or text."""
    conn = db()
    meta = conn.execute(
        "SELECT * FROM sessions WHERE session_id LIKE ?", (f"{session_id}%",)
    ).fetchone()
    if not meta:
        click.echo(red(f"  Session not found: {session_id}"))
        conn.close()
        return

    sid = meta['session_id']
    rows = conn.execute(
        "SELECT * FROM exchanges WHERE session_id=? ORDER BY exchange_index", (sid,)
    ).fetchall()

    # Parse tool_calls JSON
    exchanges = []
    for r in rows:
        d = dict(r)
        try:
            d['tool_calls'] = json.loads(d['tool_calls'] or "[]")
        except Exception:
            d['tool_calls'] = []
        try:
            d['attachments'] = json.loads(d['attachments'] or "[]")
        except Exception:
            d['attachments'] = []
        exchanges.append(d)

    conn.close()

    if fmt == "json":
        out = json.dumps({
            "session_id": sid,
            "title": meta['title'],
            "created_at": meta['created_at'],
            "workspace_id": meta['workspace_id'],
            "exchanges": exchanges
        }, indent=2)
    elif fmt == "jsonl":
        out = "\n".join(json.dumps(e) for e in exchanges)
    else:
        lines = [f"SESSION: {meta['title']}", f"ID: {sid}", f"Date: {fmt_ts(meta['created_at'])}", ""]
        for ex in exchanges:
            if ex['user_message']:
                lines.append(f"YOU [{ex['exchange_index']}] {ex['user_ts']}")
                lines.append(ex['user_message'])
                lines.append("")
            if ex['response_text']:
                lines.append("CDA")
                lines.append(ex['response_text'])
                lines.append("")
            lines.append("─" * 60)
            lines.append("")
        out = "\n".join(lines)

    if output:
        Path(output).write_text(out)
        click.echo(green(f"  Exported to {output}"))
    else:
        click.echo(out)


# ─────────────────────────────────────────────
# RAW SQL QUERY
# ─────────────────────────────────────────────

@cli.command()
@click.argument("sql")
@click.option("--limit", "-n", default=50)
def query(sql, limit):
    """Run a raw SQL query against the DB."""
    if "LIMIT" not in sql.upper():
        sql = sql.rstrip(";") + f" LIMIT {limit}"
    conn = db()
    try:
        rows = conn.execute(sql).fetchall()
        conn.close()
    except Exception as e:
        click.echo(red(f"  SQL error: {e}"))
        conn.close()
        return

    if not rows:
        click.echo(dim("  (0 rows)"))
        return

    keys = rows[0].keys()
    click.echo()
    click.echo(bold("  " + "  ".join(str(k)[:20] for k in keys)))
    click.echo(hr())
    for r in rows:
        click.echo("  " + "  ".join(truncate(str(r[k]), 30) for k in keys))
    click.echo(dim(f"\n  {len(rows)} rows"))
    click.echo()


# ─────────────────────────────────────────────
# BEHAVIORAL SIGNALS
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id", required=False, default=None)
@click.option("--type", "-t", "sig_type", default=None,
              help="Filter: correction|redirect|affirmation|approval|question")
@click.option("--limit", "-n", default=40)
def signals(session_id, sig_type, limit):
    """Show behavioral signals extracted from sessions."""
    conn = db()
    where = []
    args = []
    if session_id:
        where.append("s.session_id LIKE ?")
        args.append(session_id + "%")
    if sig_type:
        where.append("s.signal_type = ?")
        args.append(sig_type)
    clause = ("WHERE " + " AND ".join(where)) if where else ""
    sql = f"""
        SELECT s.signal_type, s.matched_keyword, s.user_message,
               s.session_id, s.ts
        FROM exchange_signals s
        {clause}
        ORDER BY s.ts DESC
        LIMIT {limit}
    """
    rows = conn.execute(sql, args).fetchall()
    conn.close()

    if not rows:
        click.echo(dim("  (no signals found)"))
        return

    click.echo()
    TYPE_COLOR = {
        'correction':  red,
        'redirect':    yellow,
        'affirmation': green,
        'approval':    cyan,
        'question':    bold,
    }
    for r in rows:
        t = r['signal_type']
        colorize = TYPE_COLOR.get(t, lambda x: x)
        label = colorize(f"[{t:<12}]")
        kw = dim(f"  kw={r['matched_keyword']:<20}")
        sid_short = r['session_id'][:8]
        msg = truncate(r['user_message'] or '', 80)
        click.echo(f"  {label}{kw}  {dim(sid_short)}  {msg}")
    click.echo()

    # Summary by type
    conn = db()
    by_type = conn.execute(
        f"""SELECT signal_type, COUNT(*) as n FROM exchange_signals
            {'WHERE session_id LIKE ?' if session_id else ''}
            GROUP BY signal_type ORDER BY n DESC""",
        ([session_id + "%"] if session_id else [])
    ).fetchall()
    conn.close()
    click.echo(bold("  Signal totals:"))
    for r in by_type:
        bar = "█" * min(r['n'], 40)
        click.echo(f"    {r['signal_type']:<14} {r['n']:>5}  {dim(bar)}")
    click.echo()


# ─────────────────────────────────────────────
# COMPACTION HISTORY
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id", required=False, default=None)
@click.option("--full", "-f", is_flag=True, help="Show full summary text")
@click.option("--limit", "-n", default=20)
def compactions(session_id, full, limit):
    """Show context compaction events (model self-summaries)."""
    conn = db()
    where = "WHERE session_id LIKE ?" if session_id else ""
    args = [session_id + "%"] if session_id else []
    sql = f"""
        SELECT session_id, turn_index, summary_length,
               context_length_before, num_rounds, summary_model,
               duration_ms, summary_text, ts
        FROM compactions
        {where}
        ORDER BY ts DESC
        LIMIT {limit}
    """
    rows = conn.execute(sql, args).fetchall()
    total = conn.execute(
        f"SELECT COUNT(*) FROM compactions {where}", args
    ).fetchone()[0] if not session_id else None
    conn.close()

    if not rows:
        click.echo(dim("  (no compactions found)"))
        return

    click.echo()
    click.echo(bold(f"  {'session':<10}  {'turn':>4}  {'ctx_before':>10}  {'rounds':>6}  {'model':<25}  {'summary_len':>11}"))
    click.echo(hr())
    for r in rows:
        sid_short = r['session_id'][:8]
        model = truncate(r['summary_model'] or 'unknown', 25)
        ctx = f"{r['context_length_before']:,}" if r['context_length_before'] else '-'
        click.echo(
            f"  {dim(sid_short):<10}  {(r['turn_index'] or 0):>4}  {ctx:>10}  "
            f"{(r['num_rounds'] or 0):>6}  {model:<25}  {(r['summary_length'] or 0):>11,}"
        )
        if full and r['summary_text']:
            wrapped = textwrap.fill(r['summary_text'][:800], width=90, initial_indent='    ', subsequent_indent='    ')
            click.echo(dim(wrapped))
            click.echo()

    click.echo()
    if total:
        click.echo(dim(f"  {total} total compaction events across all sessions"))
    click.echo()

# ─────────────────────────────────────────────
# BEHAVIOR REPORT
# ─────────────────────────────────────────────


@cli.command()
@click.option("--limit", "-n", default=20, help="Top N sessions to show")
def behavior(limit):
    """Aggregate behavioral intelligence report across all sessions."""
    conn = db()

    # Overall signal totals
    sig_totals = conn.execute(
        "SELECT signal_type, COUNT(*) as n FROM exchange_signals GROUP BY signal_type ORDER BY n DESC"
    ).fetchall()

    # Top correction keywords
    top_kw = conn.execute(
        """SELECT matched_keyword, COUNT(*) as n FROM exchange_signals
           WHERE signal_type='correction'
           GROUP BY matched_keyword ORDER BY n DESC LIMIT 15"""
    ).fetchall()

    # Sessions with most corrections
    worst_sessions = conn.execute(
        f"""SELECT sa.session_id, sa.total_corrections, sa.total_redirects,
                   sa.total_affirmations, sa.compaction_count,
                   sa.total_tokens_prompt, sa.total_tokens_completion
            FROM session_analysis sa
            WHERE sa.total_corrections > 0
            ORDER BY sa.total_corrections DESC
            LIMIT {limit}"""
    ).fetchall()

    # Session health summary
    health = conn.execute(
        """SELECT
             COUNT(*) as total,
             SUM(clean_run) as clean,
             SUM(CASE WHEN total_corrections > 0 THEN 1 ELSE 0 END) as corrected,
             SUM(total_corrections) as total_corrections,
             SUM(total_affirmations) as total_affirmations,
             SUM(compaction_count) as total_compactions,
             AVG(total_tokens_prompt) as avg_prompt_tokens
           FROM session_analysis"""
    ).fetchone()

    # Most common model
    models = conn.execute(
        "SELECT model_ids, COUNT(*) as n FROM session_analysis WHERE model_ids != '' GROUP BY model_ids ORDER BY n DESC LIMIT 5"
    ).fetchall()

    conn.close()

    click.echo()
    click.echo(bold("══════════════════════════════════════════"))
    click.echo(bold("  BEHAVIORAL INTELLIGENCE REPORT"))
    click.echo(bold("══════════════════════════════════════════"))
    click.echo()

    if health and health['total']:
        click.echo(bold("  Session Health:"))
        click.echo(f"    Total sessions analyzed:  {health['total']}")
        pct_clean = 100 * (health['clean'] or 0) / health['total']
        pct_corrected = 100 * (health['corrected'] or 0) / health['total']
        click.echo(f"    Clean runs (0 corrections): {health['clean']}  ({pct_clean:.0f}%)")
        click.echo(f"    Sessions with corrections:  {health['corrected']}  ({pct_corrected:.0f}%)")
        click.echo(f"    Total corrections issued:   {red(str(health['total_corrections'] or 0))}")
        click.echo(f"    Total affirmations:         {green(str(health['total_affirmations'] or 0))}")
        click.echo(f"    Total compactions:          {health['total_compactions'] or 0}")
        avg_pt = health['avg_prompt_tokens']
        if avg_pt:
            click.echo(f"    Avg prompt tokens/session:  {avg_pt:,.0f}")
        click.echo()

    if sig_totals:
        click.echo(bold("  Signal Distribution:"))
        for r in sig_totals:
            bar = "█" * min(r['n'] // 5, 50)
            color = red if r['signal_type'] == 'correction' else (green if r['signal_type'] == 'affirmation' else dim)
            click.echo(f"    {r['signal_type']:<14} {r['n']:>5}  {color(bar)}")
        click.echo()

    if top_kw:
        click.echo(bold("  Top Correction Triggers (what you typed to stop me):"))
        for r in top_kw:
            click.echo(f"    {r['n']:>4}×  {red(repr(r['matched_keyword']))}")
        click.echo()

    if models:
        click.echo(bold("  Models Used:"))
        for r in models:
            click.echo(f"    {r['n']:>4} sessions  {r['model_ids']}")
        click.echo()

    if worst_sessions:
        click.echo(bold(f"  Sessions With Most Corrections (top {limit}):"))
        click.echo(bold(f"    {'session':<10}  {'corr':>5}  {'redir':>6}  {'affirm':>7}  {'compact':>8}  {'prompt_tok':>12}"))
        click.echo("    " + "─" * 65)
        for r in worst_sessions:
            sid_short = r['session_id'][:8]
            pt = f"{r['total_tokens_prompt']:,}" if r['total_tokens_prompt'] else '-'
            click.echo(
                f"    {dim(sid_short):<10}  {red(str(r['total_corrections'])):>5}  "
                f"{str(r['total_redirects'] or 0):>6}  {green(str(r['total_affirmations'] or 0)):>7}  "
                f"{str(r['compaction_count'] or 0):>8}  {pt:>12}"
            )
        click.echo()


# ─────────────────────────────────────────────
# HEAT — Frustration + Pre-correction analysis
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id", required=False, default=None)
@click.option("--limit", "-n", default=20, help="Top N sessions")
@click.option("--signals", "show_signals", is_flag=True, default=False, help="Show raw signal messages")
def heat(session_id, limit, show_signals):
    """Frustration and pre-correction signal analysis.

    With no args: show hottest sessions ranked by heat_score.
    With SESSION_ID: drill into that session's signals.
    """
    conn = db()

    if session_id:
        # Drill into one session
        sid_like = session_id + "%"
        sa = conn.execute(
            """SELECT session_id, total_corrections, total_frustrations,
                      total_pre_corrections, total_redirects, heat_score
               FROM session_analysis WHERE session_id LIKE ?""",
            (sid_like,)
        ).fetchone()
        if not sa:
            click.echo(dim(f"  no data for session {session_id}"))
            conn.close()
            return

        click.echo()
        click.echo(bold(f"  Heat report: {dim(sa['session_id'][:16])}"))
        click.echo(f"    heat_score:       {_heat_bar(sa['heat_score'])}")
        click.echo(f"    corrections:      {red(str(sa['total_corrections'] or 0))}")
        click.echo(f"    frustrations:     {red(str(sa['total_frustrations'] or 0))}")
        click.echo(f"    pre-corrections:  {str(sa['total_pre_corrections'] or 0)}")
        click.echo(f"    redirects:        {str(sa['total_redirects'] or 0)}")
        click.echo()

        # Show signals grouped by type
        for sig_type in ('frustration', 'pre_correction', 'correction'):
            rows = conn.execute(
                """SELECT matched_keyword, user_message, ts
                   FROM exchange_signals
                   WHERE session_id LIKE ? AND signal_type=?
                   ORDER BY ts""",
                (sid_like, sig_type)
            ).fetchall()
            if not rows:
                continue
            color = red if sig_type in ('frustration', 'correction') else dim
            click.echo(bold(f"  {sig_type.upper()} ({len(rows)}):"))
            for r in rows:
                kw = r['matched_keyword'] or ''
                msg = (r['user_message'] or '')[:120]
                click.echo(f"    {color('[' + kw + ']'):<28} {dim(msg)}")
            click.echo()

    else:
        # Global hottest sessions
        rows = conn.execute(
            f"""SELECT sa.session_id, sa.heat_score,
                       sa.total_corrections, sa.total_frustrations,
                       sa.total_pre_corrections, sa.total_redirects,
                       sa.total_affirmations, sa.compaction_count
                FROM session_analysis sa
                WHERE sa.heat_score > 0
                ORDER BY sa.heat_score DESC
                LIMIT {limit}"""
        ).fetchall()

        # Global frustration keyword frequency
        top_frustration_kw = conn.execute(
            """SELECT matched_keyword, COUNT(*) as n
               FROM exchange_signals
               WHERE signal_type IN ('frustration', 'pre_correction')
               GROUP BY matched_keyword ORDER BY n DESC LIMIT 12"""
        ).fetchall()

        # Global totals
        totals = conn.execute(
            """SELECT
                 SUM(total_frustrations) as tf,
                 SUM(total_pre_corrections) as tpc,
                 COUNT(CASE WHEN heat_score >= 20 THEN 1 END) as hot_sessions,
                 COUNT(CASE WHEN heat_score >= 50 THEN 1 END) as very_hot,
                 AVG(heat_score) as avg_heat
               FROM session_analysis"""
        ).fetchone()

        conn.close()

        click.echo()
        click.echo(bold("══════════════════════════════════════════"))
        click.echo(bold("  HEAT REPORT — Frustration Intelligence"))
        click.echo(bold("══════════════════════════════════════════"))
        click.echo()

        if totals:
            click.echo(bold("  Overview:"))
            click.echo(f"    Total frustration signals:   {red(str(int(totals['tf'] or 0)))}")
            click.echo(f"    Total pre-correction signals:{str(int(totals['tpc'] or 0))}")
            click.echo(f"    Sessions with heat ≥ 20:     {str(int(totals['hot_sessions'] or 0))}")
            click.echo(f"    Sessions with heat ≥ 50:     {red(str(int(totals['very_hot'] or 0)))}")
            click.echo(f"    Average heat score:          {totals['avg_heat']:.1f}" if totals['avg_heat'] else "")
            click.echo()

        if top_frustration_kw:
            click.echo(bold("  Top Frustration Triggers:"))
            for r in top_frustration_kw:
                bar = "█" * min(r['n'], 30)
                click.echo(f"    {r['n']:>4}×  {red(repr(r['matched_keyword'])):<32} {dim(bar)}")
            click.echo()

        if rows:
            click.echo(bold(f"  Hottest Sessions (top {limit}):"))
            click.echo(bold(f"    {'session':<10}  {'heat':>6}  {'corr':>5}  {'frust':>6}  {'pre':>4}  {'redir':>5}  {'affirm':>7}"))
            click.echo("    " + "─" * 60)
            for r in rows:
                sid_short = r['session_id'][:8]
                heat_val = r['heat_score'] or 0
                heat_str = red(str(heat_val)) if heat_val >= 50 else (str(heat_val) if heat_val >= 20 else dim(str(heat_val)))
                click.echo(
                    f"    {dim(sid_short):<10}  {heat_str:>6}  "
                    f"{red(str(r['total_corrections'] or 0)):>5}  "
                    f"{red(str(r['total_frustrations'] or 0)):>6}  "
                    f"{str(r['total_pre_corrections'] or 0):>4}  "
                    f"{str(r['total_redirects'] or 0):>5}  "
                    f"{green(str(r['total_affirmations'] or 0)):>7}"
                )
            click.echo()
        return

    conn.close()


def _heat_bar(score):
    """Visual heat bar for a score 0-100."""
    score = score or 0
    filled = min(score // 5, 20)
    bar = "█" * filled + "░" * (20 - filled)
    label = f"{score:>3}/100"
    if score >= 50:
        return red(f"{bar} {label}")
    elif score >= 20:
        return f"{bar} {label}"
    else:
        return dim(f"{bar} {label}")


# ─────────────────────────────────────────────
# SAVED SESSIONS
# ─────────────────────────────────────────────

@cli.command()
@click.option("--limit", "-n", default=20, help="Top N sessions")
@click.option("--min-heat", default=25, help="Minimum peak_heat to qualify")
@click.option("--show-antidote", "show_antidote", is_flag=True, default=False,
              help="Show full turning-point message text")
def saved(limit, min_heat, show_antidote):
    """Saved sessions — heat that recovered. The Antidote catalog.

    Shows sessions where heat peaked then the session recovered with
    affirmations/approvals. The turning_point message is the exact
    correction that worked — the Antidote.
    """
    conn = db()

    rows = conn.execute(
        f"""SELECT sa.session_id, sa.heat_score, sa.peak_heat, sa.final_heat,
                   sa.total_corrections, sa.total_frustrations, sa.total_pre_corrections,
                   sa.total_affirmations, sa.compaction_count,
                   sa.turning_point_ts, sa.turning_point_text
            FROM session_analysis sa
            WHERE sa.saved_session = 1 AND sa.peak_heat >= {min_heat}
            ORDER BY sa.peak_heat DESC
            LIMIT {limit}"""
    ).fetchall()

    # Global stats
    stats = conn.execute(
        f"""SELECT
              COUNT(*) as total_saved,
              AVG(peak_heat) as avg_peak,
              MAX(peak_heat) as max_peak,
              SUM(total_corrections + total_frustrations + total_pre_corrections) as total_heat_signals,
              COUNT(CASE WHEN peak_heat >= 50 THEN 1 END) as very_hot_saved
            FROM session_analysis
            WHERE saved_session = 1 AND peak_heat >= {min_heat}"""
    ).fetchone()

    # Turning-point signal type breakdown — what kind of message saved them?
    antidote_types = conn.execute(
        """SELECT es.signal_type, COUNT(*) as n
           FROM session_analysis sa
           JOIN exchange_signals es
             ON es.session_id = sa.session_id AND es.ts = sa.turning_point_ts
           WHERE sa.saved_session = 1
           GROUP BY es.signal_type ORDER BY n DESC"""
    ).fetchall()

    # Top matched keywords at turning points
    antidote_kws = conn.execute(
        """SELECT es.matched_keyword, es.signal_type, COUNT(*) as n
           FROM session_analysis sa
           JOIN exchange_signals es
             ON es.session_id = sa.session_id AND es.ts = sa.turning_point_ts
           WHERE sa.saved_session = 1 AND es.matched_keyword IS NOT NULL
           GROUP BY es.matched_keyword ORDER BY n DESC LIMIT 15"""
    ).fetchall()

    conn.close()

    click.echo()
    click.echo(bold("══════════════════════════════════════════════"))
    click.echo(bold("  SAVED SESSIONS — The Antidote Catalog"))
    click.echo(bold("══════════════════════════════════════════════"))
    click.echo()

    if stats and stats['total_saved']:
        click.echo(bold("  Recovery Stats:"))
        click.echo(f"    Saved sessions:            {green(str(stats['total_saved']))}")
        click.echo(f"    Very hot saved (≥50):      {green(str(stats['very_hot_saved'] or 0))}")
        click.echo(f"    Avg peak heat:             {stats['avg_peak']:.1f}" if stats['avg_peak'] else "")
        click.echo(f"    Max peak heat:             {red(str(int(stats['max_peak'] or 0)))}")
        click.echo(f"    Total heat signals:        {str(int(stats['total_heat_signals'] or 0))}")
        click.echo()
    else:
        click.echo(dim(f"  No saved sessions found with peak_heat >= {min_heat}"))
        click.echo(dim("  Try --min-heat 15 to lower the threshold"))
        return

    if antidote_types:
        click.echo(bold("  Antidote Signal Types (what kind of message saved the session):"))
        for r in antidote_types:
            bar = "█" * min(r['n'], 25)
            click.echo(f"    {r['n']:>4}×  {r['signal_type']:<20} {dim(bar)}")
        click.echo()

    if antidote_kws:
        click.echo(bold("  Top Antidote Keywords (the phrases that worked):"))
        for r in antidote_kws:
            click.echo(f"    {r['n']:>4}×  {green(repr(r['matched_keyword'])):<30}  {dim(r['signal_type'])}")
        click.echo()

    if rows:
        click.echo(bold(f"  Saved Sessions (top {limit}, ranked by peak heat):"))
        click.echo(bold(f"    {'session':<10}  {'peak':>5}  {'corr':>5}  {'frust':>6}  {'pre':>4}  {'affirm':>7}  {'compact':>8}"))
        click.echo("    " + "─" * 62)
        for r in rows:
            sid_short = r['session_id'][:8]
            peak = r['peak_heat'] or 0
            peak_str = red(str(peak)) if peak >= 50 else str(peak)
            click.echo(
                f"    {dim(sid_short):<10}  {peak_str:>5}  "
                f"{red(str(r['total_corrections'] or 0)):>5}  "
                f"{red(str(r['total_frustrations'] or 0)):>6}  "
                f"{str(r['total_pre_corrections'] or 0):>4}  "
                f"{green(str(r['total_affirmations'] or 0)):>7}  "
                f"{str(r['compaction_count'] or 0):>8}"
            )
            if show_antidote and r['turning_point_text']:
                # Show the turning-point message (the Antidote)
                msg = r['turning_point_text'][:200].replace('\n', ' ')
                click.echo(f"        {bold('Antidote:')} {dim(msg)}")
            click.echo()
    click.echo()


# ─────────────────────────────────────────────
# TOKEN USAGE
# ─────────────────────────────────────────────

@cli.command()
@click.argument("session_id", required=False, default=None)
@click.option("--limit", "-n", default=30)
def tokens(session_id, limit):
    """Show per-request token usage for a session (or aggregate summary)."""
    conn = db()

    if session_id:
        rows = conn.execute(
            """SELECT turn_index, prompt_tokens, output_tokens, model_id, ts
               FROM token_usage WHERE session_id LIKE ?
               ORDER BY turn_index LIMIT ?""",
            (session_id + "%", limit)
        ).fetchall()
        conn.close()
        if not rows:
            click.echo(dim("  (no token data)"))
            return
        click.echo()
        click.echo(bold(f"  Token usage — session {session_id[:16]}"))
        click.echo(bold(f"  {'turn':>5}  {'prompt':>9}  {'output':>8}  model"))
        click.echo(hr())
        total_p = total_o = 0
        for r in rows:
            total_p += r['prompt_tokens'] or 0
            total_o += r['output_tokens'] or 0
            model_short = (r['model_id'] or 'unknown')[:30]
            click.echo(f"  {r['turn_index']:>5}  {(r['prompt_tokens'] or 0):>9,}  {(r['output_tokens'] or 0):>8,}  {dim(model_short)}")
        click.echo(hr())
        click.echo(bold(f"  {'TOTAL':>5}  {total_p:>9,}  {total_o:>8,}"))
        click.echo()
    else:
        # Aggregate across all sessions
        rows = conn.execute(
            f"""SELECT sa.session_id, sa.total_tokens_prompt, sa.total_tokens_completion,
                       sa.compaction_count, sa.total_corrections, sa.model_ids
                FROM session_analysis sa
                WHERE sa.total_tokens_prompt > 0
                ORDER BY sa.total_tokens_prompt DESC LIMIT {limit}"""
        ).fetchall()
        totals = conn.execute(
            "SELECT SUM(total_tokens_prompt), SUM(total_tokens_completion) FROM session_analysis"
        ).fetchone()
        conn.close()

        if not rows:
            click.echo(dim("  (no token data)"))
            return
        click.echo()
        click.echo(bold("  Top sessions by token usage:"))
        click.echo(bold(f"  {'session':<10}  {'prompt':>12}  {'output':>9}  {'compactions':>12}  {'corrections':>12}"))
        click.echo(hr())
        for r in rows:
            sid_short = r['session_id'][:8]
            pt = f"{r['total_tokens_prompt']:,}" if r['total_tokens_prompt'] else '-'
            ot = f"{r['total_tokens_completion']:,}" if r['total_tokens_completion'] else '-'
            click.echo(
                f"  {dim(sid_short):<10}  {pt:>12}  {ot:>9}  "
                f"{(r['compaction_count'] or 0):>12}  {(r['total_corrections'] or 0):>12}"
            )
        if totals and totals[0]:
            click.echo(hr())
            click.echo(bold(f"  {'ALL':>10}  {totals[0]:>12,}  {(totals[1] or 0):>9,}"))
        click.echo()


# ─────────────────────────────────────────────
# CONTROL
# ─────────────────────────────────────────────

@cli.group("control")
def control_group():
    """Inspect and query the control plane (identity, health, runs, events)."""
    pass


@control_group.command("status")
def control_status():
    """Show control DB identity snapshot."""
    from cda.kernel.control_db import CONTROL_DB
    if not CONTROL_DB.exists():
        click.echo(red("  control.db not found — run: python control/scripts/seed.py"))
        return
    conn = sqlite3.connect(CONTROL_DB)
    rows = conn.execute("SELECT key, value FROM identity ORDER BY id").fetchall()
    conn.close()
    click.echo()
    click.echo(bold("  control plane — identity"))
    click.echo(hr())
    for key, val in rows:
        click.echo(f"  {cyan(key.ljust(20))}  {val or dim('—')}")
    click.echo()


@control_group.command("health")
@click.option("--tail", default=14, show_default=True, help="Show last N check runs.")
@click.option("--check", "check_name", default=None, help="Filter to a specific check name.")
def control_health(tail, check_name):
    """Show recent selfcheck history from the health table."""
    from cda.kernel.control_db import CONTROL_DB
    if not CONTROL_DB.exists():
        click.echo(red("  control.db not found"))
        return
    conn = sqlite3.connect(CONTROL_DB)
    if check_name:
        rows = conn.execute(
            "SELECT run_at, check_name, passed, message FROM health "
            "WHERE check_name=? ORDER BY id DESC LIMIT ?",
            (check_name, tail)
        ).fetchall()
    else:
        # latest full run (by run_at) — most recent N distinct timestamps
        run_ats = [r[0] for r in conn.execute(
            "SELECT DISTINCT run_at FROM health ORDER BY run_at DESC LIMIT ?", (tail,)
        ).fetchall()]
        rows = []
        for ts in run_ats:
            batch = conn.execute(
                "SELECT run_at, check_name, passed, message FROM health WHERE run_at=? ORDER BY id",
                (ts,)
            ).fetchall()
            rows.extend(batch)
    conn.close()

    if not rows:
        click.echo(dim("  (no health history yet — run cda check)"))
        return

    click.echo()
    last_ts = None
    for run_at, name, passed, msg in rows:
        ts_short = run_at[:19].replace("T", " ")
        if ts_short != last_ts:
            click.echo(bold(f"\n  {ts_short}"))
            last_ts = ts_short
        icon = green("✓") if passed else red("✗")
        click.echo(f"    {icon}  {cyan(name.ljust(20))}  {msg or ''}")
    click.echo()


@control_group.command("runs")
@click.option("--tail", default=10, show_default=True, help="Show last N sync runs.")
def control_runs(tail):
    """Show recent sync pipeline run history."""
    from cda.kernel.control_db import CONTROL_DB
    if not CONTROL_DB.exists():
        click.echo(red("  control.db not found"))
        return
    conn = sqlite3.connect(CONTROL_DB)
    rows = conn.execute(
        "SELECT started_at, finished_at, trigger, stages, sessions, exchanges, "
        "tool_calls, vfs_files, errors, exit_code, notes "
        "FROM runs ORDER BY id DESC LIMIT ?",
        (tail,)
    ).fetchall()
    conn.close()

    if not rows:
        click.echo(dim("  (no sync runs recorded yet)"))
        return

    click.echo()
    click.echo(bold(f"  last {len(rows)} sync run(s)"))
    click.echo(hr())
    for r in rows:
        started, finished, trigger, stages, sessions, exchanges, tc, vfs, errs, exit_c, notes = r
        duration = ""
        if started and finished:
            try:
                from datetime import datetime
                s = datetime.fromisoformat(started)
                f = datetime.fromisoformat(finished)
                secs = int((f - s).total_seconds())
                duration = f"  {dim(str(secs) + 's')}"
            except Exception:
                pass
        status_icon = green("✓") if (exit_c == 0) else red("✗")
        ts = started[:19].replace("T", " ")
        click.echo(
            f"  {status_icon}  {cyan(ts)}{duration}  "
            f"sessions={bold(str(sessions or '?'))}  "
            f"exchanges={bold(str(exchanges or '?'))}  "
            f"stages={dim(stages or '?')}"
        )
        if notes:
            click.echo(f"       {dim(notes)}")
    click.echo()


@control_group.command("events")
@click.option("--tail", default=20, show_default=True, help="Show last N events.")
@click.option("--kind", default=None, help="Filter by event kind (e.g. sync.complete).")
def control_events(tail, kind):
    """Show the system event log."""
    from cda.kernel.control_db import CONTROL_DB
    if not CONTROL_DB.exists():
        click.echo(red("  control.db not found"))
        return
    conn = sqlite3.connect(CONTROL_DB)
    if kind:
        rows = conn.execute(
            "SELECT occurred_at, kind, actor, subject, detail FROM events "
            "WHERE kind=? ORDER BY id DESC LIMIT ?", (kind, tail)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT occurred_at, kind, actor, subject, detail FROM events "
            "ORDER BY id DESC LIMIT ?", (tail,)
        ).fetchall()
    conn.close()

    if not rows:
        click.echo(dim("  (no events recorded yet)"))
        return

    click.echo()
    click.echo(bold(f"  last {len(rows)} event(s)"))
    click.echo(hr())
    for occurred_at, evkind, actor, subject, detail in rows:
        ts = occurred_at[:19].replace("T", " ")
        click.echo(
            f"  {cyan(ts)}  {bold(evkind.ljust(20))}  "
            f"{dim(actor or '')}  {subject or ''}  {dim(detail or '')}"
        )
    click.echo()


# ─────────────────────────────────────────────
# SELF CHECK
# ─────────────────────────────────────────────

@cli.command("check")
@click.option("--json", "as_json", is_flag=True, help="Output results as JSON.")
@click.option("--fail-fast", is_flag=True, help="Stop at first failure.")
def check(as_json, fail_fast):
    """Run a full self-diagnostic. The system checks itself."""
    from cda.kernel.selfcheck import CHECKS
    from cda.kernel.control_db import write_health
    from datetime import datetime, timezone

    run_at = datetime.now(timezone.utc).isoformat()

    if not as_json:
        click.echo()
        click.echo(bold("  cda self-check"))
        click.echo(hr())

    results = []
    passed_all = True

    for check_fn in CHECKS:
        result = check_fn()
        results.append(result)
        passed = result["passed"]
        if not passed:
            passed_all = False

        if not as_json:
            icon  = green("✓") if passed else red("✗")
            name  = cyan(result["name"].ljust(18))
            msg   = result["message"]
            click.echo(f"  {icon}  {name}  {msg}")
            if not passed and result.get("details"):
                click.echo(f"       {dim(str(result['details'])[:120])}")

        if fail_fast and not passed:
            break

    # Write results to control DB (silent — never blocks)
    write_health(results, run_at=run_at)

    if as_json:
        import json as _json
        click.echo(_json.dumps({
            "passed": passed_all,
            "checks": results,
        }, indent=2))
        sys.exit(0 if passed_all else 1)

    click.echo(hr())
    if passed_all:
        click.echo(f"  {green(bold('All checks passed.'))}")
    else:
        failed = [r["name"] for r in results if not r["passed"]]
        click.echo(f"  {red(bold(f'{len(failed)} check(s) failed:'))} {', '.join(failed)}")
    click.echo()
    sys.exit(0 if passed_all else 1)


# ─────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────

@cli.command("setup")
@click.option("--skip-sync", "skip_sync", is_flag=True, default=False,
              help="Skip initial data ingest (run `cda sync` manually later)")
@click.option("--no-browser", "no_browser", is_flag=True, default=False,
              help="Don't open browser when the web UI starts")
def setup(skip_sync, no_browser):
    """
    Full onboarding in four steps: init → pmf install → sync → up.

    \b
    Run this once after `pip install code-data-ark`.
    If `cda` isn't on PATH yet, use the fallback:

        python3 -m cda setup

    \b
    What each step does:
      1. Init    — create ~/Library/goCosmix/apps/code-data-ark/, patch PATH
      2. Install — register a macOS LaunchAgent so CDA starts on every login
      3. Sync    — ingest all VS Code + Copilot session data into cda.db
      4. Up      — start the watcher daemon and web UI via PMF, open browser

    All processes are managed by the PMF kernel. The LaunchAgent calls
    `cda pmf up` on every login — no manual interaction needed after setup.
    """
    import shutil as _shutil
    import os as _os
    from cda.kernel.paths import (
        CDA_HOME, DATA_DIR, RUN_DIR, LOG_DIR, QUEUE_DIR,
        PMF_DIR, PMF_LOG_DIR, CONFIG_DIR, POLICY_FILE,
        GOCOSMIX_HOME, GOCOSMIX_APPS, GOCOSMIX_SYSTEM,
    )

    W = 52
    BAR = "═" * W
    bar = "─" * W
    host, port = "127.0.0.1", 10001
    url = f"http://{host}:{port}"

    click.echo()
    click.echo(bold(BAR))
    click.echo(bold("  Code Data Ark — setup"))
    click.echo(bold(BAR))
    click.echo()
    click.echo(dim("  Four steps to a fully operational CDA installation:"))
    click.echo(dim(f"    1. Init    — create {CDA_HOME}"))
    click.echo(dim("    2. Install — register macOS LaunchAgent (auto-start on login)"))
    click.echo(dim("    3. Sync    — first-run data ingest") + (dim("  [skipped]") if skip_sync else ""))
    click.echo(dim("    4. Up      — start watcher + web UI via PMF, open browser"))
    click.echo()

    # ── Step 1: Init ─────────────────────────────────────────────
    click.echo(bold(bar))
    click.echo(bold("  Step 1/4 — Init"))
    click.echo(bold(bar))
    click.echo()

    # Create full goCosmix namespace + app dirs
    dirs = [GOCOSMIX_HOME, GOCOSMIX_APPS, GOCOSMIX_SYSTEM,
            DATA_DIR, RUN_DIR, LOG_DIR, QUEUE_DIR, PMF_DIR, PMF_LOG_DIR, CONFIG_DIR]
    for d in dirs:
        existed = d.exists()
        d.mkdir(parents=True, exist_ok=True)
        if not existed:
            click.echo(f"    {green('+')}  {d}")
        else:
            click.echo(f"    {green('✓')}  {d}")

    if not POLICY_FILE.exists():
        POLICY_FILE.write_text("# CDA access policy\n# ALLOW <pattern>\n# DENY  <pattern>\n")

    # Offer migration from legacy ~/.cda/
    legacy = Path.home() / ".cda"
    if legacy.exists() and legacy != CDA_HOME:
        click.echo()
        click.echo(yellow(f"    ⚠  Legacy data found at {legacy}"))
        click.echo(yellow("       Run `cda migrate-home` after setup to move it to the new location."))

    # VS Code data dir check
    vscode_data = Path(_os.environ.get(
        "VSCODE_DATA_DIR",
        Path.home() / "Library/Application Support/Code/User",
    ))
    if vscode_data.exists():
        click.echo(f"    {green('✓')}  VS Code data dir found")
    else:
        click.echo(f"    {yellow('⚠')}  VS Code data dir not found: {vscode_data}")
        click.echo(yellow("         Set VSCODE_DATA_DIR if your data is elsewhere."))

    click.echo()
    click.echo(f"    {green('✓')}  CDA_HOME: {CDA_HOME}")
    click.echo()

    # ── PATH patch ───────────────────────────────────────────────
    # Detect where pip placed the `cda` binary and ensure it's on PATH.
    # Works whether invoked as `cda setup` or `python3 -m cda setup`.
    cda_bin_dir = None
    cda_bin = _shutil.which("cda")
    if cda_bin:
        cda_bin_dir = str(Path(cda_bin).parent)
    else:
        # pip install --user puts scripts next to python executable
        py_bin_dir = Path(sys.executable).parent
        candidate = py_bin_dir / "cda"
        if candidate.exists():
            cda_bin_dir = str(py_bin_dir)

    if cda_bin_dir and cda_bin_dir not in _os.environ.get("PATH", "").split(":"):
        export_line = f'export PATH="{cda_bin_dir}:$PATH"'
        zprofile = Path.home() / ".zprofile"
        existing = zprofile.read_text() if zprofile.exists() else ""
        if export_line not in existing:
            with open(zprofile, "a") as f:
                f.write(f"\n# goCosmix — added by cda setup\n{export_line}\n")
            click.echo(f"    {green('+')}  PATH updated in ~/.zprofile")
            click.echo(yellow("         Run `source ~/.zprofile` or open a new terminal to activate."))
        click.echo(f"    {green('✓')}  cda binary: {cda_bin_dir}/cda")
    elif cda_bin:
        click.echo(f"    {green('✓')}  cda binary on PATH: {cda_bin}")

    click.echo()

    # ── Step 2: PMF install ──────────────────────────────────────
    click.echo(bold(bar))
    click.echo(bold("  Step 2/4 — PMF install"))
    click.echo(bold(bar))
    click.echo()
    click.echo(dim("  The LaunchAgent registers CDA with macOS launchd. On every login,"))
    click.echo(dim("  launchd calls `cda pmf up` — starts watcher + web UI via PMF kernel."))
    click.echo(dim("  No terminal required after this."))
    click.echo()

    pmf_ok = False
    try:
        target = install_launchd(CDA_HOME)
        click.echo(f"    {green('✓')}  LaunchAgent: {target}")
        click.echo(f"    {green('✓')}  Loaded — CDA starts automatically on every login")
        pmf_ok = True
    except PMFKernelError as exc:
        click.echo(f"    {yellow('⚠')}  LaunchAgent registration failed: {exc}")
        click.echo(yellow("         Fix PATH then run `cda pmf install` to retry."))
    click.echo()

    # ── Step 3: Sync ─────────────────────────────────────────────
    click.echo(bold(bar))
    click.echo(bold("  Step 3/4 — Sync"))
    click.echo(bold(bar))
    click.echo()

    if skip_sync:
        click.echo(f"    {yellow('↳')}  Skipped (--skip-sync).  Run `cda sync` when ready.")
        click.echo()
    else:
        click.echo(dim("  Scanning VS Code workspaceStorage and building cda.db."))
        click.echo(dim("  First run may take a few minutes depending on session history."))
        click.echo()

        sync_failed = False
        stages = [
            ("cda.pipeline.ingest",      "Ingest       — reading VS Code storage"),
            ("cda.pipeline.reconstruct",  "Reconstruct  — building exchanges + FTS"),
            ("cda.pipeline.extract",      "Extract      — behavioral signals + tokens"),
            ("cda.pipeline.embed",        "Embed        — semantic intelligence layer"),
        ]
        for module, label in stages:
            click.echo(yellow(f"    → {label}"))
            result = subprocess.run([sys.executable, "-m", module], capture_output=False)
            if result.returncode != 0:
                click.echo(red("    ✗  Failed — sync incomplete"))
                sync_failed = True
                break
            click.echo(green("    ✓  Done"))
            click.echo()

        if not sync_failed:
            click.echo(green("    ✓  Sync complete"))
            click.echo()

    # ── Step 4: Up ───────────────────────────────────────────────
    click.echo(bold(bar))
    click.echo(bold("  Step 4/4 — Up"))
    click.echo(bold(bar))
    click.echo()
    click.echo(dim("  Starting all services through the PMF kernel."))
    click.echo(dim("  Each process is tracked, logged, and restartable via `cda pmf`."))
    click.echo()

    for svc_id, opts, label in [
        ("watcher", None,                         "Watcher daemon"),
        ("ui",      {"host": host, "port": port}, f"Web UI         →  {url}"),
    ]:
        try:
            result = kernel.start_service(svc_id, options=opts)
            click.echo(f"    {green('✓')}  {label}   pid={result['pid']}")
        except PMFKernelError as exc:
            msg = str(exc)
            if "already running" in msg.lower():
                click.echo(f"    {green('✓')}  {label}   (already running)")
            else:
                click.echo(f"    {yellow('⚠')}  {label}   {msg}")

    click.echo()

    if not no_browser:
        click.echo(dim("  Waiting for web UI..."))
        opened = wait_for_port_and_open_browser(url, host, port)
        if opened:
            click.echo(f"    {green('✓')}  Browser opened: {url}")
        else:
            click.echo(f"    {yellow('⚠')}  Server not responding yet — visit {url} manually")
        click.echo()

    # ── Done ─────────────────────────────────────────────────────
    click.echo(bold(BAR))
    click.echo(bold("  Setup complete."))
    click.echo(bold(BAR))
    click.echo()
    if pmf_ok:
        click.echo(dim("  CDA starts automatically on every login via launchd."))
    click.echo(dim("  The watcher daemon keeps your session data in sync automatically."))
    click.echo(dim(f"  Visit {url} any time to explore your data."))
    click.echo()
    click.echo(dim("  Useful commands:"))
    click.echo(dim("    cda check          — full system health diagnostic"))
    click.echo(dim("    cda sync           — re-ingest after significant new session activity"))
    click.echo(dim("    cda pmf services   — view running services and their status"))
    click.echo(dim("    cda pmf uninstall  — remove the auto-start LaunchAgent"))
    click.echo()


# ─────────────────────────────────────────────
# INIT
# ─────────────────────────────────────────────

@cli.command("init")
def init():
    """First-run setup — create ~/Library/goCosmix/apps/code-data-ark/ directory structure and validate environment."""
    from cda.kernel.paths import (
        CDA_HOME, DATA_DIR, RUN_DIR, LOG_DIR, QUEUE_DIR,
        PMF_DIR, PMF_LOG_DIR, CONFIG_DIR, POLICY_FILE,
    )
    import os

    click.echo()
    click.echo(bold("  Code Data Ark — init"))
    click.echo(hr())

    # Create directory tree
    dirs = [DATA_DIR, RUN_DIR, LOG_DIR, QUEUE_DIR, PMF_DIR, PMF_LOG_DIR, CONFIG_DIR]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        click.echo(green(f"  {d}"))

    # Write a starter policy file if none exists
    if not POLICY_FILE.exists():
        POLICY_FILE.write_text("# CDA access policy\n# ALLOW <pattern>\n# DENY  <pattern>\n")
        click.echo(green(f"  {POLICY_FILE}  (created)"))

    # Validate VS Code data dir
    vscode_data = Path(os.environ.get(
        "VSCODE_DATA_DIR",
        Path.home() / "Library/Application Support/Code/User",
    ))
    if vscode_data.exists():
        click.echo(green(f"  VS Code data dir: {vscode_data}"))
    else:
        click.echo(yellow(f"  VS Code data dir not found: {vscode_data}"))
        click.echo(yellow("  Set VSCODE_DATA_DIR if your data is elsewhere."))

    click.echo()
    click.echo(bold("  CDA_HOME: ") + str(CDA_HOME))
    click.echo()
    click.echo(dim("  Next steps:"))
    click.echo(dim("    cda pmf install  — register as a macOS LaunchAgent (auto-start on login)"))
    click.echo(dim("    cda sync         — ingest all VS Code session data"))
    click.echo(dim("    cda pmf up       — start watcher + web UI now (opens browser)"))
    click.echo(dim("    cda serve        — run web UI in foreground (opens browser)"))
    click.echo()


# ─────────────────────────────────────────────
# ENTRY
# ─────────────────────────────────────────────

def main():
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
