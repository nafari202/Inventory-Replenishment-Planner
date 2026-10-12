"""Safety stock, reorder point and order quantity for each SKU.

The Excel workbook rebuilds these numbers with formulas (NORM.S.INV, SQRT, ROUNDUP),
so the arithmetic here is kept identical to the spreadsheet.
"""
from statistics import NormalDist

import numpy as np
import pandas as pd

from . import config


def _roundup(x):
    """Round up to a whole unit, after trimming float noise (50.00000000000001 -> 50) the way Excel does."""
    return np.ceil(np.round(x, 6))


def z_score(service_level: float) -> float:
    return NormalDist().inv_cdf(service_level)


def _order_qty(prof: pd.DataFrame, out: pd.DataFrame) -> pd.DataFrame:
    """Economic order quantity, rounded up, and never less than one week of average demand."""
    annual_demand = prof["mean_weekly"] * config.WEEKS_PER_YEAR
    eoq = np.sqrt(2 * annual_demand * config.ORDER_COST / (config.HOLDING_RATE * prof["unit_cost"]))
    out["eoq"] = eoq
    out["order_qty"] = np.maximum(_roundup(eoq), _roundup(prof["mean_weekly"]))
    return out


def statistical(prof: pd.DataFrame, targets: dict | float | None = None) -> pd.DataFrame:
    """(s, Q) policy: reorder point s covers lead-time demand plus safety stock; Q is the EOQ.

    Safety stock = z x weekly std dev x sqrt(lead time), so variable SKUs carry more.
    targets: a {class: level} dict (default config.SERVICE_TARGETS) or one level for every SKU.
    """
    targets = config.SERVICE_TARGETS if targets is None else targets
    L = config.LEAD_TIME_WEEKS
    out = pd.DataFrame(index=prof.index)
    out["service_target"] = prof["abc"].map(targets) if isinstance(targets, dict) else float(targets)
    out["z"] = out["service_target"].map(z_score)
    out["safety_stock"] = out["z"] * prof["sd_weekly"] * np.sqrt(L)
    out["reorder_point"] = _roundup(prof["mean_weekly"] * L + out["safety_stock"])
    return _order_qty(prof, out)


def weeks_of_cover(prof: pd.DataFrame, weeks: float | None = None) -> pd.DataFrame:
    """Rule of thumb: safety stock = the same number of weeks of average demand for every SKU."""
    weeks = config.BASELINE_COVER_WEEKS if weeks is None else weeks
    L = config.LEAD_TIME_WEEKS
    out = pd.DataFrame(index=prof.index)
    out["safety_stock"] = prof["mean_weekly"] * weeks
    out["reorder_point"] = _roundup(prof["mean_weekly"] * (L + weeks))
    return _order_qty(prof, out)
