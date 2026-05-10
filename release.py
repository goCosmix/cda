#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VERSION_FILE = ROOT / "VERSION"
PYPROJECT_FILE = ROOT / "pyproject.toml"
SETUP_FILE = ROOT / "setup.py"
INIT_FILE = ROOT / "vscode_ark" / "__init__.py"

VERSION_PATTERN = r"\d+\.\d+\.\d+"


def read_version():
    text = VERSION_FILE.read_text().strip()
    if not re.fullmatch(VERSION_PATTERN, text):
        raise SystemExit(f"VERSION file must contain a semantic version, found: {text}")
    return text


def write_version(version: str):
    VERSION_FILE.write_text(f"{version}\n")


def replace_in_file(path: Path, pattern: str, replacement: str, multiline: bool = False):
    text = path.read_text()
    flags = re.MULTILINE if multiline else 0
    new_text, count = re.subn(pattern, replacement, text, flags=flags)
    if count == 0:
        raise SystemExit(f"Pattern not found in {path}: {pattern}")
    path.write_text(new_text)


def sync_version(version: str):
    replace_in_file(PYPROJECT_FILE, r'^(version\s*=\s*")' + VERSION_PATTERN + r'(")', rf'\g<1>{version}\g<2>', multiline=True)
    replace_in_file(SETUP_FILE, r'^(\s*version\s*=\s*")' + VERSION_PATTERN + r'(",)', rf'\g<1>{version}\g<2>', multiline=True)
    replace_in_file(INIT_FILE, r'^(\s*__version__\s*=\s*")' + VERSION_PATTERN + r'(")', rf'\g<1>{version}\g<2>', multiline=True)


def git_command(args, check=True):
    subprocess.run(["git"] + args, cwd=ROOT, check=check)


def build_package():
    subprocess.run(["python", "-m", "build", "--sdist", "--wheel"], cwd=ROOT, check=True)


def publish_package():
    subprocess.run(["python", "-m", "twine", "upload", "dist/*"], cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser(description="Release management for vscode-ark")
    parser.add_argument("--set-version", help="Set a new version and update all version sources")
    parser.add_argument("--sync", action="store_true", help="Sync version sources from VERSION file")
    parser.add_argument("--tag", action="store_true", help="Create a git tag for the current version")
    parser.add_argument("--push", action="store_true", help="Push current branch and tags to origin")
    parser.add_argument("--build", action="store_true", help="Build source and wheel distributions")
    parser.add_argument("--publish", action="store_true", help="Publish built distributions to PyPI")
    args = parser.parse_args()

    version = args.set_version or read_version()
    if args.set_version:
        write_version(version)

    if args.sync or args.set_version:
        sync_version(version)

    if args.tag:
        git_command(["tag", "-a", f"v{version}", "-m", f"Release v{version}"])

    if args.build:
        build_package()

    if args.publish:
        publish_package()

    if args.push:
        git_command(["push", "origin", "HEAD"])
        if args.tag:
            git_command(["push", "origin", "--tags"])

    print(f"Release process completed for version {version}.")


if __name__ == "__main__":
    main()
