"""
backfill.py — re-run extract + embed over sessions that are missing analysis.

Usage (CLI):
    cda backfill [--force] [--session SESSION_ID] [--dry-run]

Usage (module):
    from cda.pipeline.backfill import run_backfill
    run_backfill(conn, force=False)
"""

import sys
from datetime import datetime, timezone

from cda.ui.db.base import get_db
from cda.pipeline import extract, embed


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_backfill_candidates(conn, force=False, session_id=None):
    """Return session_ids that have VFS content but are missing analysis."""
    if session_id:
        rows = conn.execute(
            "SELECT session_id FROM sessions WHERE session_id=?", (session_id,)
        ).fetchall()
        return [r[0] for r in rows]

    if force:
        # All sessions that have a chat_session blob in vfs
        rows = conn.execute(
            """SELECT DISTINCT s.session_id FROM sessions s
               JOIN vfs v ON v.session_id = s.session_id
               WHERE v.source_type = 'chat_session'"""
        ).fetchall()
    else:
        # Sessions missing analysis OR missing signals
        rows = conn.execute(
            """SELECT DISTINCT s.session_id FROM sessions s
               JOIN vfs v ON v.session_id = s.session_id
               WHERE v.source_type = 'chat_session'
               AND (
                   s.session_id NOT IN (SELECT session_id FROM session_analysis)
                   OR s.session_id NOT IN (SELECT DISTINCT session_id FROM exchange_signals)
               )"""
        ).fetchall()
    return [r[0] for r in rows]


def backfill_session(conn, session_id, verbose=True):
    """Re-run the full extract + embed pipeline for one session."""
    blob_row = conn.execute(
        "SELECT content FROM vfs WHERE session_id=? AND source_type='chat_session'",
        (session_id,)
    ).fetchone()
    if not blob_row:
        if verbose:
            print(f"  skip {session_id[:8]}  no vfs blob")
        return False

    # Clear stale extract data
    conn.execute("DELETE FROM token_usage WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM compactions WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM exchange_signals WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM session_analysis WHERE session_id=?", (session_id,))

    # Ensure schema
    extract.ensure_schema(conn)

    # Re-extract
    n_signals, n_tokens, n_compactions = extract.process_session(conn, session_id, blob_row[0])
    extract.build_session_analysis(conn, session_id)
    conn.commit()

    # Re-embed
    try:
        embed.build_session_intelligence(conn, session_id)
        conn.commit()
    except Exception as ex:
        if verbose:
            print(f"  warn  embed failed for {session_id[:8]}: {ex}")

    if verbose:
        print(f"  ok    {session_id[:8]}  signals={n_signals} tokens={n_tokens} compactions={n_compactions}")
    return True


def run_backfill(conn=None, force=False, session_id=None, dry_run=False, verbose=True):
    """
    Backfill extract+embed for sessions missing analysis.

    Returns: dict with counts (total, processed, skipped, errors)
    """
    close_conn = conn is None
    if conn is None:
        conn = get_db()

    candidates = get_backfill_candidates(conn, force=force, session_id=session_id)
    total = len(candidates)

    if verbose:
        label = "all" if force else "missing-analysis"
        print(f"\nBackfill ({label}): {total} session(s) to process\n{'─' * 48}")

    if dry_run:
        if verbose:
            for sid in candidates:
                print(f"  dry-run  {sid[:8]}")
            print(f"\n{'─' * 48}\nDry run complete — {total} would be processed.")
        if close_conn:
            conn.close()
        return {"total": total, "processed": 0, "skipped": 0, "errors": 0, "dry_run": True}

    processed = 0
    errors = 0

    for i, sid in enumerate(candidates, 1):
        if verbose:
            print(f"[{i}/{total}]", end=" ")
        try:
            ok = backfill_session(conn, sid, verbose=verbose)
            processed += 1 if ok else 0
        except Exception as ex:
            errors += 1
            if verbose:
                print(f"  error {sid[:8]}: {ex}")

    # Build symbol index after backfill
    if processed > 0 and not dry_run:
        if verbose:
            print("\nRebuilding symbol index...")
        try:
            extract.build_symbol_index(conn)
            conn.commit()
            if verbose:
                n = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
                print(f"  symbol index: {n} symbols indexed")
        except Exception as ex:
            if verbose:
                print(f"  warn: symbol index failed: {ex}")

    skipped = total - processed - errors

    if verbose:
        print(f"\n{'─' * 48}")
        print(f"Backfill complete: {processed} processed, {skipped} skipped, {errors} errors\n")

    if close_conn:
        conn.close()

    return {"total": total, "processed": processed, "skipped": skipped, "errors": errors}


def get_pipeline_status(conn=None):
    """Return pipeline coverage metrics for the status API."""
    close_conn = conn is None
    if conn is None:
        conn = get_db()

    def count(sql, params=()):
        return conn.execute(sql, params).fetchone()[0]

    total_sessions = count("SELECT COUNT(*) FROM sessions")
    with_analysis = count("SELECT COUNT(*) FROM session_analysis")
    with_vfs = count("SELECT COUNT(DISTINCT session_id) FROM vfs WHERE source_type='chat_session'")
    with_signals = count("SELECT COUNT(DISTINCT session_id) FROM exchange_signals")
    with_tokens = count("SELECT COUNT(DISTINCT session_id) FROM token_usage")
    with_embeddings = count("SELECT COUNT(DISTINCT session_id) FROM embeddings WHERE entity_type='session'")

    total_exchanges = count("SELECT COUNT(*) FROM exchanges")
    total_signals = count("SELECT COUNT(*) FROM exchange_signals")
    total_symbols = count("SELECT COUNT(*) FROM symbols")
    total_recommendations = count("SELECT COUNT(*) FROM recommendations")
    total_alerts = count("SELECT COUNT(*) FROM anomaly_alerts")

    missing_analysis = with_vfs - with_analysis  # only count extractable sessions
    missing_signals = total_sessions - with_signals

    import os
    from cda.kernel.paths import QUEUE_DIR, PID_FILE
    queue_pending = 0
    try:
        queue_pending = len([f for f in QUEUE_DIR.iterdir() if not f.name.endswith(".completed")])
    except Exception:
        pass

    watcher_alive = False
    watcher_pid = None
    try:
        if PID_FILE.exists():
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            watcher_alive = True
            watcher_pid = pid
    except Exception:
        pass

    if close_conn:
        conn.close()

    def pct(n, total):
        return round(100 * n / total, 1) if total else 0

    return {
        "sessions": {
            "total": total_sessions,
            "with_vfs": with_vfs,
            "with_analysis": with_analysis,
            "with_signals": with_signals,
            "with_tokens": with_tokens,
            "with_embeddings": with_embeddings,
            "missing_analysis": missing_analysis,
            "missing_signals": missing_signals,
            "analysis_pct": pct(with_analysis, with_vfs),  # % of extractable sessions
            "signals_pct": pct(with_signals, with_vfs),
            "tokens_pct": pct(with_tokens, with_vfs),
            "embeddings_pct": pct(with_embeddings, total_sessions),
        },
        "totals": {
            "exchanges": total_exchanges,
            "signals": total_signals,
            "symbols": total_symbols,
            "recommendations": total_recommendations,
            "alerts": total_alerts,
        },
        "watcher": {
            "alive": watcher_alive,
            "pid": watcher_pid,
            "queue_pending": queue_pending,
        },
    }


def main():
    """CLI entry point: cda backfill"""
    import argparse
    parser = argparse.ArgumentParser(description="Backfill extract+embed for sessions missing analysis")
    parser.add_argument("--force", action="store_true", help="Re-process all sessions, not just missing ones")
    parser.add_argument("--session", metavar="SESSION_ID", help="Backfill a single session by ID")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without processing")
    parser.add_argument("--symbols-only", action="store_true", help="Only rebuild the symbol index")
    args = parser.parse_args()

    if args.symbols_only:
        conn = get_db()
        extract.ensure_schema(conn)
        print("Building symbol index...")
        extract.build_symbol_index(conn)
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
        print(f"  {n} symbols indexed")
        conn.close()
        sys.exit(0)

    result = run_backfill(
        force=args.force,
        session_id=args.session,
        dry_run=args.dry_run,
        verbose=True,
    )
    sys.exit(0 if result["errors"] == 0 else 1)


if __name__ == "__main__":
    main()
