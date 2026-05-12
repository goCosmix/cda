"""cda.pipeline.reasoning — AI cognitive quality signals.

Detects reasoning quality signals from assistant outputs and (when available)
native reasoning traces (Claude extended thinking / `reasoningText` field).

Signal taxonomy — two axes:

  POSITIVE (epistemic virtue):
    metacognitive      — AI acknowledges uncertainty or its own limits
    assumption_stated  — AI explicitly surfaces an assumption before acting
    evidence_grounded  — AI anchors claim to observed code/data, not pattern-match
    self_correcting    — AI corrects itself mid-response without user prompt
    calibrated         — AI expresses confidence proportional to evidence

  NEGATIVE (epistemic failure):
    false_certainty    — AI asserts definitively without visible basis
    silent_assumption  — AI takes a significant action without stating why
    contradiction      — AI contradicts a prior statement in the same session

  METACOGNITIVE (process transparency):
    reasoning_shown    — AI surfaces reasoning trace / thinking-aloud
    plan_stated        — AI articulates a plan before executing
    scope_checked      — AI verifies scope/context before proceeding

Cognitive Score (0–100):
  Positive signals add points. Negative signals subtract.
  Per-session aggregate: cognitive_score = min(100, max(0, weighted_sum))

  Weights:
    metacognitive:     +4
    assumption_stated: +3
    evidence_grounded: +3
    self_correcting:   +5
    calibrated:        +3
    reasoning_shown:   +4
    plan_stated:       +2
    scope_checked:     +2
    false_certainty:   -4
    silent_assumption: -2
    contradiction:     -5
"""

import re
from typing import Dict, List, Tuple

# ── Positive signal patterns (assistant output) ────────────────────────────

_METACOGNITIVE_PATTERNS = re.compile(
    r"""
    \b(
        i('m|\s+am)\s+(not\s+)?sure     # "I'm not sure" / "I am sure"
      | i\s+think\b                       # "I think"
      | i\s+believe\b                     # "I believe"
      | i\s+suspect\b                     # "I suspect"
      | i('m|\s+am)\s+inferring          # "I'm inferring"
      | i('m|\s+am)\s+guessing           # "I'm guessing"
      | likely\b                          # "likely"
      | probably\b                        # "probably"
      | i\s+should\s+(check|verify|confirm|look)  # "I should check"
      | let\s+me\s+(check|verify|confirm|look)     # "let me check"
      | unclear\s+(to\s+me|from\s+the)   # "unclear to me"
      | i\s+may\s+(be\s+wrong|have\s+missed)       # "I may be wrong"
      | not\s+100%                        # "not 100%"
      | i\s+don't\s+know\b               # "I don't know"
      | i\s+can't\s+be\s+certain         # "I can't be certain"
      | worth\s+double.checking          # "worth double-checking"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_ASSUMPTION_PATTERNS = re.compile(
    r"""
    \b(
        assuming\b                          # "assuming"
      | i('m|\s+am)\s+assuming            # "I'm assuming"
      | this\s+assumes\b                   # "this assumes"
      | given\s+that\b                     # "given that"
      | if\s+(we\s+assume|we\s+take|X\s+is\s+true)  # "if we assume"
      | based\s+on\s+(the\s+)?assumption  # "based on the assumption"
      | presupposing\b                     # "presupposing"
      | under\s+the\s+assumption          # "under the assumption"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_EVIDENCE_PATTERNS = re.compile(
    r"""
    \b(
        (because|based\s+on)\s+(the\s+)?(file|code|line|output|log|schema|table|db|data|result)  # "based on the file"
      | (line|lines?)\s+\d+               # "line 42"
      | the\s+(output|log|error|trace)\s+(shows?|says?|indicates?)  # "the output shows"
      | looking\s+at\s+the                # "looking at the"
      | from\s+the\s+(file|code|schema|output)  # "from the file"
      | (the\s+)?schema\s+(shows?|has|contains)    # "schema shows"
      | i\s+(can\s+)?see\s+(that\s+)?the           # "I can see that the"
      | this\s+(confirms?|shows?|indicates?)        # "this confirms"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SELF_CORRECTION_PATTERNS = re.compile(
    r"""
    \b(
        actually[,\s]                      # "actually,"
      | wait[,\.]\s                        # "wait, "
      | scratch\s+that\b                   # "scratch that"
      | let\s+me\s+reconsider             # "let me reconsider"
      | i\s+was\s+(wrong|incorrect|mistaken)  # "I was wrong"
      | i\s+made\s+a\s+(mistake|error)    # "I made a mistake"
      | (no,?\s+)?on\s+second\s+thought   # "on second thought"
      | correction:                        # "correction:"
      | i\s+need\s+to\s+correct\b         # "I need to correct"
      | that's\s+(not\s+)?right[,\s—]     # "that's not right"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_CALIBRATED_PATTERNS = re.compile(
    r"""
    \b(
        (this\s+)?should\s+work\b          # "should work" (hedged)
      | (this\s+)?might\s+(work|be|cause)  # "might be"
      | (this\s+)?could\s+(be|mean|cause)  # "could be"
      | i\s+(would|would\s+expect)         # "I would expect"
      | appears?\s+to\s+be\b              # "appears to be"
      | seems?\s+to\s+be\b               # "seems to be"
      | as\s+far\s+as\s+i\s+(can\s+tell|know)  # "as far as I can tell"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_REASONING_SHOWN_PATTERNS = re.compile(
    r"""
    \b(
        let\s+me\s+(think|work\s+through|break\s+this\s+down|trace|map)  # "let me think"
      | (thinking\s+through|walking\s+through|working\s+through)\s+this  # "thinking through this"
      | (the\s+)?reason\s+(is|being|for\s+this)\b     # "the reason is"
      | because\s+(of\s+this|that\s+means|this\s+means)  # "because of this"
      | this\s+is\s+(why|because)\b                    # "this is why"
      | so\s+(therefore|the\s+implication)\b           # "so therefore"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_PLAN_STATED_PATTERNS = re.compile(
    r"""
    \b(
        (here['\']s\s+)?the\s+plan\b       # "here's the plan" / "the plan"
      | plan(ned)?\s+(to|is\s+to)\b        # "plan to"
      | i('ll|\s+will)\s+(first|start\s+by|begin\s+by)  # "I'll first"
      | step\s+1\b                          # "step 1"
      | first[,\s]\s*(i('ll|'m|\s+will|\s+am)|let\s+me)\b  # "first, I'll"
      | my\s+approach\s+(is|will\s+be)\b   # "my approach is"
      | here\s+(is|are)\s+(my\s+)?the\s+(steps?|approach|plan)  # "here are the steps"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SCOPE_CHECKED_PATTERNS = re.compile(
    r"""
    \b(
        (let\s+me\s+)?check\s+(the\s+)?(current\s+)?(file|schema|context|state|code)  # "check the file"
      | (before|first)[,\s]\s*(let\s+me\s+)?(read|look\s+at|check|verify)  # "before I read"
      | i('ll|\s+need\s+to|\s+want\s+to)\s+(first\s+)?(read|look\s+at|check|verify)  # "I'll first check"
      | to\s+(understand|confirm|verify)\s+(the\s+)?(context|scope|current\s+state)  # "to understand the context"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ── Negative signal patterns ───────────────────────────────────────────────

_FALSE_CERTAINTY_PATTERNS = re.compile(
    r"""
    \b(
        (this\s+)?definitely\s+(will|won|is|has|does)  # "this definitely will"
      | (this\s+)?certainly\s+(will|is|means|has)      # "certainly will"
      | always\s+(works?|is|does|returns?)\b            # "always works"
      | guaranteed\s+to\b                               # "guaranteed to"
      | (there\s+is|there['']s)\s+no\s+(way|doubt|question\s+that)  # "there's no way"
      | obviously\b                                     # "obviously"
      | (this|that)\s+is\s+(always|definitely|certainly)\s+(the\s+)?(right|correct|best)  # "this is always the right"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# ── Signal registry ────────────────────────────────────────────────────────

REASONING_SIGNAL_PATTERNS: List[Tuple[str, re.Pattern, str, int]] = [
    # (signal_type, pattern, description, weight)
    ("metacognitive",     _METACOGNITIVE_PATTERNS,   "AI acknowledges uncertainty or limits",           4),
    ("assumption_stated", _ASSUMPTION_PATTERNS,      "AI explicitly surfaces an assumption",            3),
    ("evidence_grounded", _EVIDENCE_PATTERNS,        "AI anchors claim to observed artifact",           3),
    ("self_correcting",   _SELF_CORRECTION_PATTERNS, "AI corrects itself without user prompt",          5),
    ("calibrated",        _CALIBRATED_PATTERNS,      "AI uses proportional confidence markers",         3),
    ("reasoning_shown",   _REASONING_SHOWN_PATTERNS, "AI surfaces reasoning process",                   4),
    ("plan_stated",       _PLAN_STATED_PATTERNS,     "AI states a plan before executing",               2),
    ("scope_checked",     _SCOPE_CHECKED_PATTERNS,   "AI verifies scope/context before proceeding",     2),
    ("false_certainty",   _FALSE_CERTAINTY_PATTERNS, "AI asserts definitively without visible basis",  -4),
]

REASONING_WEIGHTS: Dict[str, int] = {sig: w for sig, _, _, w in REASONING_SIGNAL_PATTERNS}


def classify_assistant_message(
    content: str,
    reasoning_text: str = "",
) -> List[Tuple[str, str]]:
    """
    Detect reasoning quality signals in an assistant message.

    Analyses both the `content` (final response) and `reasoning_text`
    (native extended-thinking trace when present).

    Returns list of (signal_type, matched_excerpt) tuples.
    One signal of each type per message maximum.
    """
    combined = (reasoning_text + "\n" + content).strip()
    if not combined:
        return []

    signals = []
    seen = set()

    for sig_type, pattern, _desc, _weight in REASONING_SIGNAL_PATTERNS:
        if sig_type in seen:
            continue
        m = pattern.search(combined)
        if m:
            signals.append((sig_type, m.group(0).strip()[:80]))
            seen.add(sig_type)

    return signals


def detect_contradictions(
    messages: List[Tuple[str, str]],  # [(content, reasoning_text), ...]
) -> List[Tuple[int, int, str]]:
    """
    Heuristic contradiction detection across a session's assistant messages.
    Looks for explicit negation of prior definitive statements.

    Returns list of (earlier_index, later_index, excerpt) tuples.
    Lightweight — not NLP, just pattern anchoring.
    """
    contradictions = []
    definite_claims: List[Tuple[int, str]] = []  # (index, claim_text)

    _CLAIM_PATTERN = re.compile(
        r"(?:this|the)\s+\w+\s+(?:is|are|will|does|has)\s+[\w\s]{3,40}[.!]",
        re.IGNORECASE,
    )
    _NEGATE_PATTERN = re.compile(
        r"\b(actually|no,|wait,|scratch that|i was wrong|that'?s not right)\b",
        re.IGNORECASE,
    )

    for idx, (content, _reasoning) in enumerate(messages):
        if _NEGATE_PATTERN.search(content) and definite_claims:
            # Flag the most recent prior claim as potentially contradicted
            prior_idx, prior_text = definite_claims[-1]
            contradictions.append((prior_idx, idx, prior_text[:80]))

        for m in _CLAIM_PATTERN.finditer(content):
            definite_claims.append((idx, m.group(0)))

    return contradictions


def compute_reasoning_score(signal_counts: Dict[str, int]) -> int:
    """
    Compute cognitive score (0–100) from aggregated signal counts.
    Positive signals add; negative signals subtract.
    """
    raw = sum(
        signal_counts.get(sig, 0) * w
        for sig, w in REASONING_WEIGHTS.items()
    )
    return max(0, min(100, raw))


def build_session_reasoning(conn, session_id: str) -> Dict:
    """
    Extract and persist reasoning signals for a session.

    Reads assistant.message rows from transcript_events, runs signal
    detection, stores results in reasoning_signals table, and upserts
    reasoning_score into session_analysis.

    Returns summary dict.
    """
    import json as _json

    # Ensure schema
    conn.executescript(REASONING_SCHEMA)

    rows = conn.execute(
        """SELECT request_id, ts, data_json FROM transcript_events
           WHERE session_id = ? AND event_type = 'assistant.message'
           ORDER BY ts""",
        (session_id,),
    ).fetchall()

    if not rows:
        return {"session_id": session_id, "messages_analyzed": 0, "signals": {}}

    signal_rows = []
    all_messages = []

    for request_id, ts, data_json in rows:
        try:
            data = _json.loads(data_json).get("data", {})
        except Exception:
            continue
        content = data.get("content", "")
        reasoning_text = data.get("reasoningText", "")
        all_messages.append((content, reasoning_text))

        sigs = classify_assistant_message(content, reasoning_text)
        for sig_type, excerpt in sigs:
            signal_rows.append((
                session_id, request_id, ts,
                sig_type, excerpt,
                1 if REASONING_WEIGHTS.get(sig_type, 0) > 0 else -1,
            ))

    # Contradiction pass
    contradictions = detect_contradictions(all_messages)
    for earlier_idx, later_idx, excerpt in contradictions:
        signal_rows.append((
            session_id, None, None,
            "contradiction", excerpt, -1,
        ))

    # Upsert signals
    conn.execute(
        "DELETE FROM reasoning_signals WHERE session_id = ?", (session_id,)
    )
    conn.executemany(
        """INSERT INTO reasoning_signals
           (session_id, request_id, ts, signal_type, excerpt, valence)
           VALUES (?, ?, ?, ?, ?, ?)""",
        signal_rows,
    )

    # Aggregate
    sig_counts: Dict[str, int] = {}
    for _, _, _, sig_type, _, _ in signal_rows:
        sig_counts[sig_type] = sig_counts.get(sig_type, 0) + 1

    score = compute_reasoning_score(sig_counts)

    # Update session_analysis with reasoning_score
    conn.execute(
        """UPDATE session_analysis
           SET reasoning_score = ?, reasoning_analyzed_at = datetime('now')
           WHERE session_id = ?""",
        (score, session_id),
    )

    return {
        "session_id": session_id,
        "messages_analyzed": len(rows),
        "signals": sig_counts,
        "reasoning_score": score,
    }


# ── Schema ─────────────────────────────────────────────────────────────────

REASONING_SCHEMA = """
CREATE TABLE IF NOT EXISTS reasoning_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    request_id      TEXT,
    ts              TEXT,
    signal_type     TEXT NOT NULL,
    excerpt         TEXT,
    valence         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_reasoning_session
    ON reasoning_signals(session_id);
CREATE INDEX IF NOT EXISTS idx_reasoning_type
    ON reasoning_signals(signal_type);
"""
