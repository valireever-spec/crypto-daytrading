"""
Phase 324: Factor Calculator

Calculate financial factors (momentum, value, quality, volatility, size)
for factor-based attribution analysis.
"""

import logging
from typing import Dict, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class FactorCalculator:
    """Calculate financial factors for attribution."""

    @staticmethod
    def calculate_momentum(returns: pd.Series, lookback: int = 60) -> float:
        """
        Calculate momentum factor (price trend).

        Parameters:
        -----------
        returns : pd.Series
            Daily returns (%)
        lookback : int
            Lookback period in days

        Returns:
        --------
        Momentum score (-1 to +1)
        """
        if len(returns) < lookback:
            return 0

        recent = returns.tail(lookback)
        momentum_return = (1 + recent / 100).prod() - 1

        # Normalize to [-1, 1] using tanh
        momentum = np.tanh(momentum_return * 2)
        return momentum

    @staticmethod
    def calculate_value_factor(
        current_price: float,
        book_value: float,
        earnings: float,
    ) -> float:
        """
        Calculate value factor (P/B, P/E ratios).

        Parameters:
        -----------
        current_price : float
            Current stock price
        book_value : float
            Book value per share
        earnings : float
            Earnings per share (annual)

        Returns:
        --------
        Value score (-1 = expensive, +1 = cheap)
        """
        scores = []

        # Price-to-Book: lower is better
        if book_value > 0:
            pb = current_price / book_value
            # Normalize: 0.5 = cheap (+1), 2.0 = expensive (-1)
            pb_score = 1 - np.tanh((pb - 1.25) / 0.75)
            scores.append(pb_score)

        # Price-to-Earnings: lower is better
        if earnings > 0:
            pe = current_price / earnings
            # Normalize: PE=10 = cheap, PE=30 = expensive
            pe_score = 1 - np.tanh((pe - 20) / 10)
            scores.append(pe_score)

        return np.mean(scores) if scores else 0

    @staticmethod
    def calculate_quality_factor(
        roe: float,  # Return on Equity %
        debt_to_equity: float,
        current_ratio: float,
    ) -> float:
        """
        Calculate quality factor (profitability, leverage, liquidity).

        Parameters:
        -----------
        roe : float
            Return on Equity (%)
        debt_to_equity : float
            Debt-to-Equity ratio
        current_ratio : float
            Current ratio (current assets / current liabilities)

        Returns:
        --------
        Quality score (-1 = poor quality, +1 = high quality)
        """
        scores = []

        # ROE: higher is better (>15% is good)
        roe_score = np.tanh((roe - 10) / 10)
        scores.append(roe_score)

        # D/E: lower is better (<1.0 is good)
        de_score = 1 - np.tanh(debt_to_equity)
        scores.append(de_score)

        # Current ratio: 1.0-2.0 is ideal
        cr_score = 1 - np.tanh((current_ratio - 1.5) / 0.5) if current_ratio > 0 else 0
        scores.append(cr_score)

        return np.mean(scores)

    @staticmethod
    def calculate_volatility_factor(returns: pd.Series, lookback: int = 60) -> float:
        """
        Calculate volatility factor (risk).

        Parameters:
        -----------
        returns : pd.Series
            Daily returns (%)
        lookback : int
            Lookback period in days

        Returns:
        --------
        Volatility score (-1 = high vol, +1 = low vol)
        """
        if len(returns) < lookback:
            return 0

        recent_vol = returns.tail(lookback).std()

        # Normalize: high vol (>3%) = -1, low vol (<1%) = +1
        vol_score = 1 - np.tanh((recent_vol - 2) / 1)
        return vol_score

    @staticmethod
    def calculate_size_factor(market_cap: float) -> float:
        """
        Calculate size factor (market capitalization).

        Parameters:
        -----------
        market_cap : float
            Market capitalization in USD

        Returns:
        --------
        Size score (-1 = large cap, +1 = small cap)
        """
        # Log-scale market cap
        log_cap = np.log10(market_cap) if market_cap > 0 else 0

        # Large cap (10B): log_cap ~ 10, Small cap (100M): log_cap ~ 8
        # -1 = large, +1 = small
        size_score = (8 - log_cap) / 2
        return np.clip(size_score, -1, 1)

    @staticmethod
    def calculate_all_factors(
        returns: pd.Series,
        price: float,
        book_value: float,
        earnings: float,
        roe: float,
        debt_to_equity: float,
        current_ratio: float,
        market_cap: float,
        lookback: int = 60,
    ) -> Dict[str, float]:
        """
        Calculate all factors for a security.

        Returns:
        --------
        {
            "momentum": score,
            "value": score,
            "quality": score,
            "volatility": score,
            "size": score
        }
        """
        return {
            "momentum": FactorCalculator.calculate_momentum(returns, lookback),
            "value": FactorCalculator.calculate_value_factor(price, book_value, earnings),
            "quality": FactorCalculator.calculate_quality_factor(roe, debt_to_equity, current_ratio),
            "volatility": FactorCalculator.calculate_volatility_factor(returns, lookback),
            "size": FactorCalculator.calculate_size_factor(market_cap),
        }

    @staticmethod
    def standardize_factors(factors: Dict[str, float]) -> Dict[str, float]:
        """
        Standardize factors to have mean 0, std 1.

        Parameters:
        -----------
        factors : dict
            {symbol: {factor_name: score}}

        Returns:
        --------
        Standardized factors
        """
        standardized = {}

        # For each factor across all symbols
        for factor_name in ["momentum", "value", "quality", "volatility", "size"]:
            scores = [f.get(factor_name, 0) for f in factors.values()]

            mean = np.mean(scores)
            std = np.std(scores)

            # Standardize
            for symbol, factor_dict in factors.items():
                if symbol not in standardized:
                    standardized[symbol] = {}

                score = factor_dict.get(factor_name, 0)
                standardized_score = (score - mean) / (std + 1e-6)
                standardized[symbol][factor_name] = standardized_score

        return standardized

    @staticmethod
    def calculate_factor_returns(
        symbol_returns: Dict[str, float],  # symbol -> return %
        symbol_factors: Dict[str, Dict[str, float]],  # symbol -> {factor: score}
    ) -> Dict[str, float]:
        """
        Calculate realized returns for each factor (cross-sectional regression).

        Parameters:
        -----------
        symbol_returns : dict
            {symbol: return %}
        symbol_factors : dict
            {symbol: {factor_name: score}}

        Returns:
        --------
        {factor_name: period_return %}
        """
        factor_returns = {}

        # Get all factors
        all_factors = set()
        for factors in symbol_factors.values():
            all_factors.update(factors.keys())

        # For each factor, calculate weighted return
        for factor_name in all_factors:
            exposures = []
            returns = []

            for symbol in symbol_factors.keys():
                if symbol in symbol_returns:
                    exposure = symbol_factors[symbol].get(factor_name, 0)
                    ret = symbol_returns[symbol]

                    exposures.append(exposure)
                    returns.append(ret)

            if exposures and returns:
                # Regression: return ~ factor_exposure
                # Simple: factor_return = Cov(exposure, return) / Var(exposure)
                exposures_array = np.array(exposures)
                returns_array = np.array(returns)

                cov = np.cov(exposures_array, returns_array)[0, 1]
                var = np.var(exposures_array)

                factor_return = cov / (var + 1e-6) if var > 0 else 0
                factor_returns[factor_name] = factor_return

        return factor_returns
