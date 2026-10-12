"""Replay a reorder policy week by week against actual 2011 demand.

Each week: receive orders due this week, ship what's on hand (unmet demand is a lost sale),
then if inventory position (on hand + on order) is at or below the reorder point,
order enough multiples of Q to lift it back above. Orders arrive LEAD_TIME_WEEKS later.
Every SKU starts the year just after a delivery: safety stock plus one order quantity on hand.
"""
import numpy as np
import pandas as pd

from . import config


def run(prof: pd.DataFrame, pol: pd.DataFrame, demand: pd.DataFrame, keep_history: bool = False):
    L = config.LEAD_TIME_WEEKS
    d = demand.loc[pol.index].to_numpy()
    n, weeks = d.shape
    rop = pol["reorder_point"].to_numpy()
    q = pol["order_qty"].to_numpy()
    on_hand = np.ceil(pol["safety_stock"].clip(lower=0).to_numpy()) + q
    pipeline = np.zeros((n, L))  # column j arrives at the start of week t + 1 + j

    sold = np.zeros((n, weeks))
    end_on_hand = np.zeros((n, weeks))
    orders = np.zeros(n)
    history = {"on_hand": end_on_hand, "sold": sold} if keep_history else None

    for t in range(weeks):
        on_hand += pipeline[:, 0]
        pipeline = np.column_stack([pipeline[:, 1:], np.zeros(n)])
        ship = np.minimum(on_hand, d[:, t])
        on_hand -= ship
        sold[:, t] = ship
        position = on_hand + pipeline.sum(axis=1)
        k = np.where(position <= rop, np.floor((rop - position) / q) + 1, 0)
        pipeline[:, L - 1] += k * q
        orders += k > 0
        end_on_hand[:, t] = on_hand

    cost = prof.loc[pol.index, "unit_cost"].to_numpy()
    price = prof.loc[pol.index, "avg_price"].to_numpy()
    years = weeks / config.WEEKS_PER_YEAR
    res = pd.DataFrame(index=pol.index)
    res["demand_units"] = d.sum(axis=1)
    res["sold_units"] = sold.sum(axis=1)
    res["lost_units"] = res["demand_units"] - res["sold_units"]
    res["fill_rate"] = np.where(res["demand_units"] > 0, res["sold_units"] / res["demand_units"], 1.0)
    res["demand_value"] = res["demand_units"] * price
    res["sold_value"] = res["sold_units"] * price
    res["stockout_weeks"] = ((d - sold) > 0).sum(axis=1)
    res["avg_on_hand_units"] = end_on_hand.mean(axis=1)
    res["avg_inventory_value"] = res["avg_on_hand_units"] * cost
    res["orders"] = orders
    res["holding_cost"] = res["avg_inventory_value"] * config.HOLDING_RATE * years
    res["ordering_cost"] = orders * config.ORDER_COST
    return (res, history) if keep_history else res


def summarize(res: pd.DataFrame, prof: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    """Totals overall or by class. Fill rate is weighted by sales value."""
    data = res.join(prof[["abc", "xyz"]])
    groups = [data.assign(_all="All")] if not by else [data]
    keys = by or ["_all"]
    g = groups[0].groupby(keys).agg(
        skus=("demand_units", "size"), demand_value=("demand_value", "sum"), sold_value=("sold_value", "sum"),
        lost_units=("lost_units", "sum"), stockout_weeks=("stockout_weeks", "sum"),
        avg_inventory_value=("avg_inventory_value", "sum"), orders=("orders", "sum"),
        holding_cost=("holding_cost", "sum"), ordering_cost=("ordering_cost", "sum"))
    g["fill_rate"] = g["sold_value"] / g["demand_value"]
    g["total_cost"] = g["holding_cost"] + g["ordering_cost"]
    return g
