"""
Setup script for MelodyMind package.
"""

from pathlib import Path

from setuptools import find_packages, setup


PROJECT_ROOT = Path(__file__).parent
README_PATH = PROJECT_ROOT / "README.md"
long_description = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""

INSTALL_REQUIRES = [
    "numpy>=1.21.0",
    "librosa>=0.9.0",
    "soundfile>=0.11.0",
    "pretty-midi>=0.2.10",
    "mido>=1.2.10",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.27",
    "python-multipart>=0.0.9",
]

EXTRAS_REQUIRE = {
    "basic-pitch": ["basic-pitch>=0.2.0"],
    "crepe": ["crepe>=0.0.14"],
    "dev": [
        "pytest>=7.0.0",
        "pytest-cov>=3.0.0",
        "black>=22.0.0",
        "flake8>=4.0.0",
        "mypy>=0.950",
    ],
}

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
    install_requires=INSTALL_REQUIRES,
    extras_require=EXTRAS_REQUIRE,
    entry_points={
        "console_scripts": [
            "melonymind=melonymind.cli:main",
            "melonymind-prepare-melody-data=melonymind.training.prepare_melody_ranker_data:main",
            "melonymind-train-melody-ranker=melonymind.training.train_melody_ranker:main",
            "melonymind-webapp=melonymind.webapp.cli:main",
        ],
    },
)
