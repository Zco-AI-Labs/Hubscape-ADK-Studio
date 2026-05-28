import os
from setuptools import setup, find_packages

# Read version dynamically from single source of truth
version_file = os.path.join("hubscape_adk", "version.txt")
if os.path.exists(version_file):
    with open(version_file, "r") as f:
        version = f.read().strip()
else:
    version = "1.0.0"

setup(
    name="hubscape-adk",
    version=version,
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "hubscape_adk": ["holodeck/*.html", "version.txt"],
    },
    install_requires=[
        "fastapi",
        "uvicorn",
        "google-genai",
        "pydantic",
        "jinja2",
        "requests",
        "python-dotenv"
    ],
    entry_points={
        "console_scripts": [
            "hubscape-adk=hubscape_adk.run_sandbox:main",
            "hubscape-adk-local=hubscape_adk.run_sandbox:main",
        ],
    },
)
