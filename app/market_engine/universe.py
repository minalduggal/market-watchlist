"""
Master asset universe definition.
Contains realistic baseline metrics: sector classification, historical volatility (sigma),
30-day average daily volume (ADV), beta against SPY, and 52-week ranges.
"""

from typing import Dict, Any

UNIVERSE: Dict[str, Dict[str, Any]] = {
    "NVDA": {
        "name": "NVIDIA Corporation",
        "sector": "Semiconductors & Accelerated Computing",
        "base_price": 128.50,
        "daily_volatility": 0.038,  # 3.8% expected daily move
        "adv": 55_000_000,
        "beta": 2.10,
        "fifty_two_week_high": 140.76,
        "fifty_two_week_low": 75.60,
    },
    "AAPL": {
        "name": "Apple Inc.",
        "sector": "Consumer Electronics & Services",
        "base_price": 224.20,
        "daily_volatility": 0.016,  # 1.6% expected daily move
        "adv": 48_000_000,
        "beta": 1.05,
        "fifty_two_week_high": 237.23,
        "fifty_two_week_low": 164.08,
    },
    "MSFT": {
        "name": "Microsoft Corporation",
        "sector": "Enterprise Cloud & Software",
        "base_price": 448.90,
        "daily_volatility": 0.015,
        "adv": 22_000_000,
        "beta": 0.98,
        "fifty_two_week_high": 468.35,
        "fifty_two_week_low": 309.45,
    },
    "GOOGL": {
        "name": "Alphabet Inc.",
        "sector": "Search & Cloud Infrastructure",
        "base_price": 166.40,
        "daily_volatility": 0.021,
        "adv": 26_000_000,
        "beta": 1.12,
        "fifty_two_week_high": 191.75,
        "fifty_two_week_low": 120.21,
    },
    "AMZN": {
        "name": "Amazon.com, Inc.",
        "sector": "E-Commerce & AWS Cloud",
        "base_price": 182.15,
        "daily_volatility": 0.022,
        "adv": 38_000_000,
        "beta": 1.18,
        "fifty_two_week_high": 201.20,
        "fifty_two_week_low": 118.35,
    },
    "TSLA": {
        "name": "Tesla, Inc.",
        "sector": "EV & Autonomous Systems",
        "base_price": 218.80,
        "daily_volatility": 0.042,  # 4.2% high beta volatility
        "adv": 72_000_000,
        "beta": 2.45,
        "fifty_two_week_high": 271.00,
        "fifty_two_week_low": 138.80,
    },
    "SPY": {
        "name": "SPDR S&P 500 ETF Trust",
        "sector": "Broad Market Benchmark",
        "base_price": 558.60,
        "daily_volatility": 0.009,  # 0.9% low volatility benchmark
        "adv": 65_000_000,
        "beta": 1.00,
        "fifty_two_week_high": 565.16,
        "fifty_two_week_low": 410.07,
    },
    "QQQ": {
        "name": "Invesco QQQ Trust (Nasdaq 100)",
        "sector": "Large Cap Tech ETF",
        "base_price": 482.30,
        "daily_volatility": 0.013,
        "adv": 42_000_000,
        "beta": 1.25,
        "fifty_two_week_high": 503.52,
        "fifty_two_week_low": 351.36,
    },
    "JNJ": {
        "name": "Johnson & Johnson",
        "sector": "Defensive Healthcare & Pharma",
        "base_price": 164.50,
        "daily_volatility": 0.009,  # 0.9% defensive
        "adv": 8_500_000,
        "beta": 0.52,
        "fifty_two_week_high": 175.90,
        "fifty_two_week_low": 143.16,
    },
    "SO": {
        "name": "The Southern Company",
        "sector": "Regulated Utilities (Ultra Low Beta)",
        "base_price": 88.20,
        "daily_volatility": 0.008,  # 0.8% very low volatility
        "adv": 4_200_000,
        "beta": 0.40,
        "fifty_two_week_high": 91.50,
        "fifty_two_week_low": 63.80,
    },
    "XLE": {
        "name": "Energy Select Sector SPDR Fund",
        "sector": "Energy & Oil Commodities",
        "base_price": 89.40,
        "daily_volatility": 0.017,
        "adv": 16_000_000,
        "beta": 0.78,
        "fifty_two_week_high": 99.00,
        "fifty_two_week_low": 79.10,
    },
    "BTC-USD": {
        "name": "Bitcoin USD",
        "sector": "Digital Assets / Crypto",
        "base_price": 63450.00,
        "daily_volatility": 0.048,  # 4.8% high volatility
        "adv": 28_000_000_000,
        "beta": 1.85,
        "fifty_two_week_high": 73750.00,
        "fifty_two_week_low": 26500.00,
    },
    "ETH-USD": {
        "name": "Ethereum USD",
        "sector": "Smart Contract Platform",
        "base_price": 2480.00,
        "daily_volatility": 0.055,  # 5.5% high volatility
        "adv": 15_000_000_000,
        "beta": 2.10,
        "fifty_two_week_high": 4090.00,
        "fifty_two_week_low": 1520.00,
    },
}
