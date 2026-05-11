.PHONY: help install install-dev test test-cov lint format clean build publish

help:
	@echo "Available commands:"
	@echo "  install     - Install the package"
	@echo "  install-dev - Install with development dependencies"
	@echo "  test        - Run tests"
	@echo "  test-cov    - Run tests with coverage"
	@echo "  lint        - Run linters"
	@echo "  format      - Format code"
	@echo "  clean       - Clean build artifacts"
	@echo "  build       - Build distribution"
	@echo "  publish     - Publish to PyPI"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=cda --cov-report=html --cov-report=term

lint:
	flake8 cda tests
	mypy cda

format:
	black cda tests
	isort cda tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf cda/__pycache__/
	rm -rf tests/__pycache__/

build:
	python -m build

publish: clean build
	twine upload dist/*

release: clean
	python bin/release.py --sync --build
	git add version pyproject.toml cda/__init__.py changelog.md bin/release.py
	git commit -m "Release version $(shell cat version)"
	python bin/release.py --tag
	git push origin HEAD --tags
	python bin/release.py --publish
