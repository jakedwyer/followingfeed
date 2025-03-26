from setuptools import setup, find_packages

setup(
    name="followfeed",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        # Read requirements from requirements.txt
        line.strip()
        for line in open("requirements.txt")
        if not line.startswith("#") and line.strip()
    ],
    entry_points={
        "console_scripts": [
            "followfeed=followfeed.core.main:main",
        ],
    },
    python_requires=">=3.10",
)
