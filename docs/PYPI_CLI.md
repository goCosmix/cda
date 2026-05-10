# PyPI CLI Guide

The `cda pypi` command group provides secure, integrated PyPI publishing for vscode-ark.

## Token Management

### Via Environment Variable (recommended for CI/CD)

```bash
export PYPI_TOKEN="pypi-AgEIcHlwaS5vcmc..."
cda pypi publish
```

### Via Interactive Setup (for local development)

```bash
cda pypi setup
```

This stores your token securely in `~/.vscode-ark/pypi.json` with restricted permissions (chmod 0600).

## Commands

### Check Configuration

Verify your PyPI token is configured and see the current version:

```bash
cda pypi check
```

Output:
```
  ✓ PyPI token configured
  Version: 2.0.0
```

### View Current Version

```bash
cda pypi version
```

### Publish Current Build

Publishes pre-built distributions from the `dist/` directory:

```bash
cda pypi publish
```

### Build and Publish

Builds distributions (sdist + wheel) and publishes in one command:

```bash
cda pypi build-publish
```

## Release Workflow

Typical release process using the integrated tools:

```bash
# 1. Set version
python release.py --set-version 2.1.0 --tag --push

# 2. Build and publish
cda pypi build-publish

# Or separately:
python release.py --build
cda pypi publish
```

## Security Notes

- **Environment Variable**: Recommended for CI/CD pipelines. Token is never written to disk.
- **Local Storage**: Token saved in `~/.vscode-ark/pypi.json` with mode `0600` (owner read/write only).
- **Priority**: Environment variable takes precedence over local config file.

## Troubleshooting

### Token Not Found

```bash
# Check if PYPI_TOKEN is set
echo $PYPI_TOKEN

# Or check local config
cat ~/.vscode-ark/pypi.json
```

### Build Fails

Ensure you're in the vscode-ark directory and dependencies are installed:

```bash
cd vscode-ark
pip install -e .
```

### Publish Fails

Verify token validity:

```bash
cda pypi check
```

If unconfigured, run:

```bash
cda pypi setup
```
