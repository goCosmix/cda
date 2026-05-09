#!/usr/bin/env python3
import sqlite3, os

conn = sqlite3.connect('/Volumes/intel/vscode-ark/vscode-ark.db')
conn.row_factory = sqlite3.Row

print('=== Sessions per workspace in DB (top 20) ===')
for r in conn.execute('SELECT workspace_id, COUNT(*) n FROM sessions GROUP BY workspace_id ORDER BY n DESC LIMIT 20').fetchall():
    print(f'  {r[0][:16]}  {r[1]} sessions')

total = conn.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
ws_with_sessions = conn.execute('SELECT COUNT(DISTINCT workspace_id) FROM sessions').fetchone()[0]
ws_no_sessions = conn.execute('SELECT COUNT(*) FROM workspaces WHERE workspace_id NOT IN (SELECT DISTINCT workspace_id FROM sessions)').fetchone()[0]
print(f'\n  Total sessions in DB: {total}  across {ws_with_sessions} workspaces  ({ws_no_sessions} workspaces have 0 sessions)')

print()
print('=== session_storage coverage ===')
has_any  = conn.execute('SELECT COUNT(*) FROM session_storage WHERE has_transcript=1 OR has_chat_session=1 OR has_debug_log=1 OR has_tool_outputs=1 OR has_edit_session=1').fetchone()[0]
has_none = conn.execute('SELECT COUNT(*) FROM session_storage WHERE has_transcript=0 AND has_chat_session=0 AND has_debug_log=0 AND has_tool_outputs=0 AND has_edit_session=0').fetchone()[0]
print(f'  Sessions with at least 1 real file:  {has_any}')
print(f'  Sessions with NO files (index-only): {has_none}')

print()
print('=== VFS counts by type ===')
for r in conn.execute('SELECT source_type, COUNT(*) n FROM vfs GROUP BY source_type ORDER BY n DESC').fetchall():
    print(f'  {r[0]:<22} {r[1]}')

def vfs_count(t):
    return conn.execute('SELECT COUNT(*) FROM vfs WHERE source_type=?', (t,)).fetchone()[0]

ws_mem_in_db = conn.execute('SELECT COUNT(*) FROM memory_files WHERE scope != "global"').fetchone()[0]

print()
print('=== On-disk counts vs DB ===')
home = os.path.expanduser('~')
vs_root = os.path.join(home, 'Library/Application Support/Code/User/workspaceStorage')
ws_dirs = [d for d in os.listdir(vs_root) if os.path.isdir(os.path.join(vs_root, d))]

cs_disk = 0
tr_disk = 0
edit_disk = 0
ws_mem_disk = 0
sem_disk = 0
ft_disk = 0
tool_disk = 0

for ws in ws_dirs:
    ws_path = os.path.join(vs_root, ws)
    copilot_path = os.path.join(ws_path, 'GitHub.copilot-chat')

    # chatSessions
    cs_dir = os.path.join(ws_path, 'chatSessions')
    if os.path.isdir(cs_dir):
        cs_disk += len([f for f in os.listdir(cs_dir) if f.endswith('.jsonl')])

    # transcripts
    tr_dir = os.path.join(copilot_path, 'transcripts')
    if os.path.isdir(tr_dir):
        tr_disk += len([f for f in os.listdir(tr_dir) if f.endswith('.jsonl')])

    # editSessions
    edit_dir = os.path.join(ws_path, 'chatEditingSessions')
    if os.path.isdir(edit_dir):
        edit_disk += len([x for x in os.listdir(edit_dir) if os.path.isdir(os.path.join(edit_dir, x))])

    # tool outputs
    tool_dir = os.path.join(copilot_path, 'chat-session-resources')
    if os.path.isdir(tool_dir):
        for s_dir in os.listdir(tool_dir):
            s_path = os.path.join(tool_dir, s_dir)
            if os.path.isdir(s_path):
                for t_dir in os.listdir(s_path):
                    t_path = os.path.join(s_path, t_dir)
                    if os.path.isdir(t_path) and os.path.exists(os.path.join(t_path, 'content.txt')):
                        tool_disk += 1

    # workspace memory files
    mem_dir = os.path.join(copilot_path, 'memory-tool', 'memories')
    if os.path.isdir(mem_dir):
        for root2, dirs2, files2 in os.walk(mem_dir):
            ws_mem_disk += len(files2)

    # semantic index
    if os.path.exists(os.path.join(copilot_path, 'workspace-chunks.db')):
        sem_disk += 1

    # full-text index
    if any(f.startswith('local-index') for f in os.listdir(ws_path)):
        ft_disk += 1

print(f'  chatSessions .jsonl     disk: {cs_disk:>5}   VFS: {vfs_count("chat_session"):>5}   gap: {cs_disk - vfs_count("chat_session")}')
print(f'  transcripts .jsonl      disk: {tr_disk:>5}   VFS: {vfs_count("transcript"):>5}   gap: {tr_disk - vfs_count("transcript")}')
print(f'  editSession dirs        disk: {edit_disk:>5}   VFS: {vfs_count("edit_state"):>5}   gap: {edit_disk - vfs_count("edit_state")}')
print(f'  tool output files       disk: {tool_disk:>5}   VFS: {vfs_count("tool_output"):>5}   gap: {tool_disk - vfs_count("tool_output")}')
print(f'  workspace memory files  disk: {ws_mem_disk:>5}   DB:  {ws_mem_in_db:>5}   gap: {ws_mem_disk - ws_mem_in_db}')
print(f'  workspace-chunks.db     disk: {sem_disk:>5}   (intentionally excluded — path-only)')
print(f'  local-index* DBs        disk: {ft_disk:>5}   (intentionally excluded — path-only)')
conn.close()
