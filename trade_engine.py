# trade_engine.py
import random


def preview_buy(
    mint: str, symbol: str, sol_amount: float, slippage_bps: int
) -> tuple[float, float]:
    """
    Returns (est_qty_tokens, est_price_tokens_per_SOL_inverse)
    Here we mock: pretend price = X tokens per 1 SOL, add slippage pessimistically.
    """
    base_tokens_per_SOL = 1000.0  # mock; replace with price quote from provider
    slip = 1 - (slippage_bps / 10000.0)
    qty = sol_amount * base_tokens_per_SOL * slip
    price_token_in_SOL = 1.0 / base_tokens_per_SOL / slip
    return qty, price_token_in_SOL


def execute_buy(
    mint: str, symbol: str, sol_amount: float, slippage_bps: int
) -> tuple[float, float]:
    """
    Returns (filled_qty_tokens, avg_fill_price_in_SOL_per_token)
    Mock fills with tiny randomness.
    """
    qty, px = preview_buy(mint, symbol, sol_amount, slippage_bps)
    qty *= random.uniform(0.995, 1.005)
    return qty, px


def preview_sell(
    mint: str, symbol: str, qty_tokens: float, slippage_bps: int
) -> tuple[float, float]:
    base_tokens_per_SOL = 1000.0
    slip = 1 - (slippage_bps / 10000.0)
    sol_out = (qty_tokens / base_tokens_per_SOL) * slip
    price_token_in_SOL = 1.0 / base_tokens_per_SOL / slip
    return sol_out, price_token_in_SOL


def execute_sell(
    mint: str, symbol: str, qty_tokens: float, slippage_bps: int
) -> tuple[float, float]:
    sol_out, px = preview_sell(mint, symbol, qty_tokens, slippage_bps)
    sol_out *= random.uniform(0.995, 1.005)
    return sol_out, px
