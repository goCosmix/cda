# Usage Examples

## Basic Commands

### Initialize and Start Monitoring

```bash
# Initial setup - ingests all VS Code data
cda sync

# Start the live watcher for real-time monitoring
cda watch start

# Check status
cda status
```

### Browse Sessions

```bash
# List all sessions (newest first)
cda sessions

# Show details for a specific session
cda session abc123def456

# Show all sessions for a workspace
cda workspace my-workspace

# List all workspaces
cda workspaces
```

## Search and Analysis

### Full-Text Search

```bash
# Search for specific topics
cda search "error handling"

# Search with context
cda search "async await" --full

# Limit results
cda search "typescript" --limit 50
```

### Signal Analysis

```bash
# Show all behavioral signals
cda signals

# Show signals for a specific session
cda signals abc123def456

# Filter by signal type
cda signals --type correction --limit 20

# Show only frustration signals
cda signals --type frustration
```

### Heat Analysis

```bash
# Show hottest sessions (highest frustration)
cda heat

# Show heat for specific session
cda heat abc123def456 --signals

# Show sessions that recovered from high heat
cda saved

# Only show very hot sessions (heat >= 50)
cda heat --limit 20
```

## Advanced Analysis

### Behavioral Intelligence

```bash
# Aggregate behavioral report
cda behavior

# Show top correction triggers
cda behavior --limit 10

# Analyze compaction events
cda compactions --full

# Show edit session analytics
cda edits
```

### Token and Usage Analysis

```bash
# Overall token usage
cda tokens

# Token usage for specific session
cda tokens abc123def456

# Show sessions with highest token consumption
cda tokens --limit 20
```

### Code Symbol Search

```bash
# Search for functions
cda code-search "def process" --symbol

# Search with path filter
cda code-search "handler" --symbol --path "src/*.py"

# Limit workspace
cda code-search "create" --symbol --workspace my-workspace --limit 20
```

## Data Export

### Export Formats

```bash
# Export as JSON
cda export abc123def456 --format json --output session.json

# Export as JSONL (one exchange per line)
cda export abc123def456 --format jsonl --output exchanges.jsonl

# Export as readable text
cda export abc123def456 --format text --output session.txt

# Print to stdout
cda export abc123def456 --format text
```

### Replay Conversations

```bash
# Print session as readable conversation
cda replay abc123def456

# Save to file
cda replay abc123def456 > conversation.txt
```

## Policy Management

### Access Control

```bash
# Allow specific patterns
cda policy allow "project-a"
cda policy allow "*.py"

# Deny sensitive data
cda policy deny "password"
cda policy deny "api-key"

# List current policies
cda policy list

# Search with policies applied
cda search "database" --limit 10  # Filters results by policies
```

## Advanced Queries

### Raw SQL Queries

```bash
# Get session statistics
cda query "SELECT COUNT(*) as session_count, SUM(exchange_count) as total_exchanges FROM sessions"

# Find sessions with many corrections
cda query "SELECT session_id, total_corrections FROM session_analysis WHERE total_corrections > 10 ORDER BY total_corrections DESC LIMIT 20"

# Analyze signal distribution
cda query "SELECT signal_type, COUNT(*) as count FROM exchange_signals GROUP BY signal_type ORDER BY count DESC"

# Find sessions with high token usage
cda query "SELECT session_id, total_tokens_prompt, total_tokens_completion FROM session_analysis WHERE total_tokens_prompt > 10000 ORDER BY total_tokens_prompt DESC"
```

## Live Monitoring

### Start and Manage Watcher

```bash
# Start live monitoring daemon
cda watch start

# Check daemon status
cda status

# Stop daemon
cda watch stop

# Restart daemon
cda watch restart

# View queue status
cda status  # Shows pending and completed operations
```

## System Administration

### Statistics and Health

```bash
# System overview
cda stats

# Memory file management
cda memory

# Rebuild search index
cda reconstruct

# Full rebuild (slow - ingests all data)
cda sync
```

### VFS Operations

```bash
# List VFS blobs for session
cda vfs ls abc123def456

# Examine VFS blob content
cda vfs cat blob123456

# Get VFS storage summary
cda vfs types
```

## Practical Workflows

### Debugging a Frustrating Session

```bash
# Find sessions with high frustration
cda heat

# Examine top session
cda session <session_id>

# Show signals that contributed to heat
cda signals <session_id> --full

# Export for detailed analysis
cda export <session_id> --format json

# Check if it recovered
cda saved --limit 1
```

### Finding Common Issues

```bash
# What causes most corrections?
cda signals --type correction | head -20

# Which conversations mention errors?
cda search "error" --limit 50

# Pattern analysis
cda query "SELECT matched_keyword, COUNT(*) FROM exchange_signals WHERE signal_type='correction' GROUP BY matched_keyword ORDER BY COUNT(*) DESC LIMIT 20"
```

### Performance Analysis

```bash
# Sessions with highest token usage
cda tokens --limit 10

# Sessions with most compactions
cda query "SELECT session_id, compaction_count, total_tokens_prompt FROM session_analysis WHERE compaction_count > 5 ORDER BY compaction_count DESC"

# Model efficiency
cda query "SELECT model_ids, AVG(total_tokens_prompt) as avg_prompt, AVG(total_tokens_completion) as avg_completion FROM session_analysis GROUP BY model_ids"
```

### Quality Assurance

```bash
# Measure agent performance
cda behavior

# Identify sessions that recovered well
cda saved

# Analyze correction patterns
cda signals --type correction --limit 100

# Check for regression
cda heat --limit 20
```

## Tips and Tricks

### Using with Unix Tools

```bash
# Filter results with grep
cda search "async" | grep "error"

# Count results
cda sessions | wc -l

# Sort results
cda tokens | sort -k2 -nr

# Extract specific fields
cda signals | awk '{print $1, $2}'
```

### Scripting

```bash
# Process multiple sessions
for session in $(cda sessions | awk '{print $1}'); do
  echo "Processing $session..."
  cda export $session --format jsonl --output "session_$session.jsonl"
done

# Generate report
cda behavior > behavior_report.txt
cda heat >> behavior_report.txt
cda tokens >> behavior_report.txt
```

### Monitoring Over Time

```bash
# Take baseline
cda stats > baseline_$(date +%s).txt

# Compare after changes
cda stats > current.txt
diff baseline_*.txt current.txt
```

## Common Patterns

### Session Investigation

```bash
# 1. Find the session
cda heat | head -1  # Get hottest session

# 2. Examine it
cda session <id>

# 3. Analyze signals
cda signals <id> --full

# 4. Export for detailed review
cda export <id> --format text
```

### Data Analysis

```bash
# 1. Get overview
cda stats

# 2. Find patterns
cda behavior

# 3. Deep dive
cda query "SELECT ... FROM ..."

# 4. Export for external tools
cda export <id> --format json
```

### Quality Monitoring

```bash
# Daily check
alias cda-daily='cda behavior && echo "---" && cda heat --limit 5'

# Weekly summary
cda stats && echo "---" && cda tokens --limit 20

# Monthly deep dive
cda query "SELECT * FROM session_analysis ORDER BY heat_score DESC LIMIT 100"
```
