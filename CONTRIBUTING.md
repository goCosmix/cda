# Contributing to VS Code Ark

We welcome contributions! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on ideas, not personal criticism
- Support others in the community

## Getting Started

### Clone and setup

```bash
git clone https://github.com/goCosmix/vscode-ark.git
cd vscode-ark
```

### Setup Development Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
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
vscode-ark/
├── vscode_ark/          # Main package
│   ├── cli.py          # Command-line interface (1800+ lines)
│   └── __init__.py     # Package metadata
├── ingest.py           # VS Code data ingestion (~200 lines)
├── reconstruct.py      # Conversation processing (~150 lines)
├── extract.py          # Signal analysis (~200 lines)
├── watcher.py          # Live monitoring (~250 lines)
├── audit.py            # Analysis utilities (~100 lines)
├── parse_edits.py      # Edit parsing (~150 lines)
├── tests/              # Test suite
├── docs/               # Documentation
└── .github/workflows/  # CI/CD configuration
```

## Key Components

### CLI (vscode_ark/cli.py)
- Entry point for command-line interface
- Uses Click framework for command routing
- Implements 25+ commands for analysis and management
- ~1800 lines of code

### Data Pipeline
- **ingest.py**: Reads VS Code storage, creates VFS blobs
- **reconstruct.py**: Structures raw data into conversations
- **extract.py**: Analyzes patterns and computes metrics

### Live Monitoring
- **watcher.py**: Monitors file changes, maintains queue
- **parse_edits.py**: Parses edit session information

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

1. Update version in `vscode_ark/__init__.py` and `pyproject.toml`
2. Update CHANGELOG.md with release notes
3. Create release commit: `git commit -m "Release v0.1.0"`
4. Create git tag: `git tag v0.1.0`
5. Push changes: `git push && git push --tags`
6. Build package: `make build`
7. Publish: `make publish`

## Additional Resources

- [Python Style Guide (PEP 8)](https://www.python.org/dev/peps/pep-0008/)
- [Git Commit Messages](https://chris.beams.io/posts/git-commit/)
- [Click Documentation](https://click.palletsprojects.com/)
- [SQLite Best Practices](https://www.sqlite.org/bestpractice.html)

---

Thank you for contributing to VS Code Ark! 🎉
