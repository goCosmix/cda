#!/usr/bin/env python3
"""
Setup script for vscode-ark.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="vscode-ark",
    version="0.1.0",
    author="Ernie Butcher",
    author_email="ernie@fiosii.com",
    description="VS Code/Copilot Chat session intelligence analysis system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/goCosmix/vscode-ark",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "watchfiles>=0.20",
        "click>=8.0",
        "sentence-transformers>=2.2.2",
        "numpy>=1.26",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "pytest-cov",
            "black",
            "isort",
            "flake8",
            "mypy",
        ],
        "test": [
            "pytest>=7.0",
            "pytest-cov",
        ],
    },
    entry_points={
        "console_scripts": [
            "cda=vscode_ark.cli:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)