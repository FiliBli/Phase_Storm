from setuptools import setup, find_packages

setup(
    name="phase-storm",
    version="0.1.0",
    packages=find_packages(),
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={
        "console_scripts": [
            "phase-storm=phase_storm.cli:main",
        ]
    },
)
