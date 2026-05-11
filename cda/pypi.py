"""
PyPI integration for vscode-ark release management.

Handles secure token management and PyPI interactions.
"""

import os
import json
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


class PyPIManager:
    """Manages PyPI token and publish operations."""

    def __init__(self):
        self.token = self._load_token()
        self.version_file = ROOT_DIR / "VERSION"

    def _load_token(self) -> str:
        """Load PyPI token from environment or config file."""
        # Priority: env var > config file
        if token := os.getenv("PYPI_TOKEN"):
            return token

        config_file = Path.home() / ".cda" / "pypi.json"
        if config_file.exists():
            try:
                config = json.loads(config_file.read_text())
                return config.get("token", "")
            except (json.JSONDecodeError, IOError):
                pass

        return ""

    def save_token(self, token: str, remember: bool = False) -> None:
        """Save PyPI token for future use."""
        if remember:
            config_dir = Path.home() / ".cda"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_file = config_dir / "pypi.json"
            config_file.write_text(json.dumps({"token": token}, indent=2))
            config_file.chmod(0o600)  # Read/write for owner only
            self.token = token

    def is_configured(self) -> bool:
        """Check if PyPI token is configured."""
        return bool(self.token)

    def get_current_version(self) -> str:
        """Get current package version."""
        return self.version_file.read_text().strip()

    def publish(self, dist_dir: str = "dist") -> bool:
        """Publish to PyPI using twine."""
        if not self.is_configured():
            raise RuntimeError("PyPI token not configured. Set PYPI_TOKEN or run 'cda pypi setup'")

        dist_path = ROOT_DIR / dist_dir
        if not dist_path.exists():
            raise FileNotFoundError(f"Distribution directory not found: {dist_path}")

        # Use twine with token
        env = os.environ.copy()
        env["TWINE_USERNAME"] = "__token__"
        env["TWINE_PASSWORD"] = self.token

        try:
            subprocess.run(
                ["python", "-m", "twine", "upload", f"{dist_path}/*"],
                cwd=ROOT_DIR,
                check=True,
                env=env,
            )
            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"PyPI publish failed: {e}")

    def build_and_publish(self) -> bool:
        """Build distributions and publish to PyPI."""
        # Build distributions
        try:
            subprocess.run(
                ["python", "-m", "build", "--sdist", "--wheel"],
                cwd=ROOT_DIR,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Build failed: {e}")

        # Publish
        return self.publish()


def setup_pypi_token() -> None:
    """Interactive setup for PyPI token."""
    import getpass

    print("\n=== PyPI Token Setup ===")
    print("Obtain your token from: https://pypi.org/manage/account/token/")
    print()

    token = getpass.getpass("Enter PyPI API token: ").strip()
    if not token:
        print("Setup cancelled.")
        return

    remember = input("Save token for future use? (y/n): ").lower() == "y"
    manager = PyPIManager()
    manager.save_token(token, remember=remember)

    if remember:
        print("✓ Token saved to ~/.cda/pypi.json")
    else:
        print("✓ Token configured for this session")
