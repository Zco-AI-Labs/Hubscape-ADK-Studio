from setuptools import setup, find_packages

setup(
    name="hubscape-adk",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "hubscape_adk": ["holodeck/*.html"],
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
        ],
    },
)
