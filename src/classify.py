"""Weekly demand by SKU, and ABC / XYZ classification."""
import numpy as np
import pandas as pd

from . import config


def weekly_demand(df: pd.DataFrame, weeks: pd.DatetimeIndex) -> pd.DataFrame:
    """Units sold per SKU per week, with zeros for weeks a SKU didn't sell."""
    sub = df[df["Week"].isin(weeks)]
    table = sub.pivot_table(index="StockCode", columns="Week", values="Quantity", aggfunc="sum", fill_value=0)
    return table.reindex(columns=weeks, fill_value=0).astype(float)


def sku_profile(df: pd.DataFrame, demand: pd.DataFrame) -> pd.DataFrame:
    """One row per SKU sold in the calibration year: revenue, price, weekly demand statistics."""
    year = df[df["Week"].isin(config.CALIBRATION_WEEKS)]
    sales = year.groupby("StockCode").agg(revenue=("Revenue", "sum"), units=("Quantity", "sum"))
    desc = year.groupby("StockCode")["Description"].agg(lambda s: s.dropna().mode().iat[0] if s.notna().any() else "")
    prof = sales.join(desc.rename("description"))
    prof["avg_price"] = prof["revenue"] / prof["units"]
    prof["unit_cost"] = prof["avg_price"] * config.COST_RATIO
    d = demand.loc[prof.index]
    prof["mean_weekly"] = d.mean(axis=1)
    prof["sd_weekly"] = d.std(axis=1, ddof=1)
    prof["cv"] = prof["sd_weekly"] / prof["mean_weekly"]
    prof["weeks_sold"] = (d > 0).sum(axis=1)
    return prof


def abc_xyz(prof: pd.DataFrame) -> pd.DataFrame:
    prof = prof.sort_values("revenue", ascending=False).copy()
    share = prof["revenue"] / prof["revenue"].sum()
    prof["revenue_share"] = share
    prof["cum_share"] = share.cumsum()
    before = prof["cum_share"] - share  # share of revenue from higher-ranked SKUs
    prof["abc"] = np.select([before < config.ABC_CUTOFFS["A"], before < config.ABC_CUTOFFS["B"]], ["A", "B"], "C")
    prof["xyz"] = np.select([prof["cv"] <= config.XYZ_CUTOFFS["X"], prof["cv"] <= config.XYZ_CUTOFFS["Y"]], ["X", "Y"], "Z")
    prof["rank"] = np.arange(1, len(prof) + 1)
    return prof


def matrix(prof: pd.DataFrame) -> pd.DataFrame:
    """SKU count and revenue share for each ABC x XYZ cell."""
    g = prof.groupby(["abc", "xyz"]).agg(skus=("revenue", "size"), revenue=("revenue", "sum")).reset_index()
    g["revenue_share"] = g["revenue"] / prof["revenue"].sum()
    return g
