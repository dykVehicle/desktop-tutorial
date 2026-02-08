from setuptools import setup, find_packages

setup(
    name="quant-trading-agent",
    version="0.1.0",
    description="量化交易智能体系统 - 模块化多策略协同交易框架",
    author="Quant Agent Team",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "pyyaml>=6.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
        ],
    },
)
