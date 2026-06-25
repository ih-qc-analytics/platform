# Approximate mid-market rates — update periodically.
# These are used ONLY when Frankfurter is unreachable after all retries.
# Search logs for APPROX_FX_RATE to find rows that need manual correction.
FALLBACK_RATES: dict[tuple[str, str], float] = {
    ("MXN", "USD"): 0.050,  # ~20 MXN/USD
    ("COP", "USD"): 0.000245,  # ~4,080 COP/USD
    ("COP", "MXN"): 0.0049,  # ~204 COP/MXN
    ("PEN", "USD"): 0.270,  # ~3.7 PEN/USD
    ("PEN", "MXN"): 5.40,  # ~0.185 MXN/PEN
}
