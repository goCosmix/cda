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
	pytest source/tests/ -v

test-cov:
	pytest source/tests/ -v --cov=cda --cov-report=html --cov-report=term

lint:
	flake8 source/cda source/tests
	mypy source/cda

format:
	black source/cda source/tests
	isort source/cda source/tests

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .pytest_cache/
	rm -rf __pycache__/
	rm -rf source/cda/__pycache__/
	rm -rf source/tests/__pycache__/

build:
	python -m build

publish: clean build
	twine upload dist/*

release: clean
	python source/bin/release.py --sync --build
	git add VERSION pyproject.toml source/cda/__init__.py CHANGELOG.md source/bin/release.py
	git commit -m "Release version $(shell cat VERSION)"
	python source/bin/release.py --tag
	git push origin HEAD --tags
	python source/bin/release.py --publish
