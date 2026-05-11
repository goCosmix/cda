# Contributing to Code Data Ark

We welcome contributions! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on ideas, not personal criticism
- Support others in the community

## Getting Started

### Clone and setup

```bash
git clone https://github.com/goCosmix/cda.git
cd cda/source
```

### Setup Development Environment

```bash
pip install -e ".[dev]"
# or
make install-dev
```

### Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

## Development Workflow

### Making Changes

1. Make your changes in the feature branch
2. Add or update tests for new functionality
3. Ensure all tests pass: `make test`
4. Format code: `make format`
5. Run linters: `make lint`

### Writing Tests

- Place tests in `tests/` directory
- Use descriptive test names: `test_<feature>_<scenario>()`
- Include docstrings explaining what's tested
- Aim for >80% code coverage

Example:
```python
def test_search_returns_results_matching_query():
    """Test that search returns sessions containing the query string."""
    # Arrange
    expected_query = "error handling"
    
    # Act
    results = search(expected_query)
    
    # Assert
    assert len(results) > 0
    assert all(expected_query.lower() in str(r).lower() for r in results)
```

### Code Style

- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 100 characters
- Use meaningful variable names
- Add docstrings to all public functions

Example:
```python
def compute_heat_score(signals: List[Signal]) -> int:
    """
    Compute heat score from behavioral signals.
    
    Args:
        signals: List of behavioral signals detected in session
        
    Returns:
        Heat score (0-100) indicating user frustration level
    """
    total_weight = sum(HEAT_WEIGHT[s.signal_type] for s in signals)
    return min(100, total_weight)
```

## Commit Guidelines

- Write clear, descriptive commit messages
- Use present tense: "Add feature" not "Added feature"
- Reference issues when relevant: "Fix #123"
- Keep commits focused and atomic

Example:
```
Add policy enforcement to search results

- Implement check_policy() function for allow/deny patterns
- Filter search results based on active policies
- Add policy command group with allow/deny/list subcommands
- Include policy filtering in cda search command

Fixes #42
```

## Pull Request Process

1. **Update documentation** - Update README or docs if needed
2. **Add tests** - Ensure new functionality has test coverage
3. **Update CHANGELOG** - Add entry under "Unreleased" section
4. **Verify quality** - Run `make test && make lint && make format`
5. **Create PR** - Provide clear description of changes
6. **Respond to reviews** - Address feedback promptly

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Enhancement
- [ ] Documentation

## Testing
- [ ] Added/updated tests
- [ ] All tests passing
- [ ] Tested locally

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] CHANGELOG updated
- [ ] No breaking changes
```

## Issues and Bug Reports

### Report a Bug

Create an issue with:
- **Title**: Clear, specific description
- **Reproduction steps**: Step-by-step instructions
- **Expected behavior**: What should happen
- **Actual behavior**: What actually happens
- **Environment**: Python version, OS, etc.

### Request a Feature

Create an issue with:
- **Title**: Feature name
- **Motivation**: Why this feature is needed
- **Use case**: How it would be used
- **Alternatives**: Other solutions considered

## Project Structure

Understanding the codebase:

```
cda/
├── .gitignore
├── source/                  # all tracked code lives here
│   ├── cda/                 # Python package
│   │   ├── __init__.py
│   │   ├── pipeline/        # data pipeline stages
│   │   │   ├── ingest.py
│   │   │   ├── reconstruct.py
│   │   │   ├── extract.py
│   │   │   ├── embed.py
│   │   │   ├── watcher.py
│   │   │   └── parse_edits.py
│   │   ├── ui/              # interfaces
│   │   │   ├── cli.py
│   │   │   └── web.py
│   │   └── kernel/          # system management
│   │       ├── pmf_kernel.py
│   │       └── selfcheck.py
│   ├── bin/
│   │   └── release.py       # version sync and release automation
│   ├── tests/
│   ├── docs/
│   ├── pyproject.toml
│   └── makefile
├── local/               # runtime state (gitignored)
│   ├── data/            # cda.db
│   ├── logs/
│   ├── queue/
│   ├── run/             # pid files
│   ├── config/
│   └── pmf/             # pmf runtime state
└── control/             # management artifacts (gitignored)
    ├── data/            # control.db
    ├── scripts/         # seed.py
    ├── audit/
    └── scan/
```

## Key Components

### CLI (`cda/ui/cli.py`)
- Entry point for command-line interface
- Uses Click framework for command routing
- Implements 40+ commands for analysis and management

### Data Pipeline
- **pipeline/ingest.py**: Reads VS Code storage, creates VFS blobs
- **pipeline/reconstruct.py**: Structures raw data into conversations
- **pipeline/extract.py**: Analyzes patterns and computes metrics
- **pipeline/embed.py**: Semantic embeddings, session summaries, anomaly alerts

### Live Monitoring
- **pipeline/watcher.py**: Monitors file changes, maintains queue
- **pipeline/parse_edits.py**: Parses edit session information

### System Management
- **kernel/pmf_kernel.py**: Service lifecycle, PID/log management, runtime state
- **kernel/selfcheck.py**: System health checks and install validation
- **ui/web.py**: Browser dashboard for all CLI features

## Testing Strategy

### Unit Tests
- Test individual functions in isolation
- Mock external dependencies
- Located in `tests/test_*.py`

### Integration Tests
- Test components working together
- Use real database (in-memory SQLite)
- Verify end-to-end data flow

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
make test-cov

# Run specific test
python -m pytest tests/test_basic.py::test_signal_patterns_import -v
```

## Documentation

- **README.md** - Main project documentation
- **CHANGELOG.md** - Version history and changes
- **Code comments** - Inline explanations for complex logic
- **Docstrings** - Function and module documentation
- **Examples** - Usage examples in `/docs/examples/`

## Performance Considerations

- Database uses WAL mode for concurrent reads
- FTS5 indexing for fast full-text search
- Gzip compression for storage efficiency
- Incremental updates via watcher daemon

## Security

- No secrets in repository
- Use environment variables for sensitive data
- Validate all user inputs
- Keep dependencies updated

## Asking for Help

- Check existing issues and PRs
- Read the documentation
- Ask questions in issues with `[question]` tag
- Join discussions for general topics

## Release Process

1. Set new version: `python bin/release.py --set-version X.Y.Z`
2. Update `changelog.md` with release notes
3. Build and tag: `python bin/release.py --build --tag --push`
4. Publish: `python bin/release.py --publish`

## Additional Resources

- [Python Style Guide (PEP 8)](https://www.python.org/dev/peps/pep-0008/)
- [Git Commit Messages](https://chris.beams.io/posts/git-commit/)
- [Click Documentation](https://click.palletsprojects.com/)
- [SQLite Best Practices](https://www.sqlite.org/bestpractice.html)

---

Thank you for contributing to Code Data Ark!
