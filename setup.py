"""
Setup script for MelodyMind package.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with open(requirements_path) as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith("#")
        ]

setup(
    name="melonymind",
    version="0.1.0",
    author="CrazyKoalar",
    author_email="",
    description="AI-powered music transcription library - Convert audio to sheet music",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CrazyKoalar/MelodyMind",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Musicians",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Multimedia :: Sound/Audio :: Analysis",
        "Topic :: Multimedia :: Sound/Audio :: MIDI",
    ],
    python_requires=">=3.8",
    install_requires=[
        "numpy>=1.21.0",
        "librosa>=0.9.0",
        "soundfile>=0.11.0",
        "pretty-midi>=0.2.10",
        "mido>=1.2.10",
    ],
    extras_require={
        "basic-pitch": ["basic-pitch>=0.2.0"],
        "crepe": ["crepe>=0.0.14"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=3.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
    },
    entry_points={
        "console_scripts": [
            "melonymind=melonymind.cli:main",
        ],
    },
)
