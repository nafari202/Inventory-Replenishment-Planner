"""Run the full analysis: clean data, classify SKUs, set policies, backtest, write charts and the workbook.

Usage:  python run_pipeline.py          (then scripts/excel_finalize.ps1 to calculate the workbook)
        python run_pipeline.py --check  (after finalizing: confirm Excel matches Python)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src import charts, classify, config, data, policy, simulate, workbook  # noqa: E402

WORKBOOK = config.OUTPUT_DIR / "Inventory_Replenishment_Planner.xlsx"


def main(check_only: bool = False):
    raw = data.load_raw()
    df, steps = data.clean(raw)
    calib = classify.weekly_demand(df, config.CALIBRATION_WEEKS)
    test = classify.weekly_demand(df, config.TEST_WEEKS)
    prof = classify.abc_xyz(classify.sku_profile(df, calib))
    pol_all = policy.statistical(prof)

    if check_only:
        print(json.dumps(workbook.check(WORKBOOK, prof, pol_all), indent=2))
        return

    planned = prof.index[prof.index.isin(test.index[test.sum(axis=1) > 0])]
    plan_prof = prof.loc[planned]
    test_demand = test.reindex(planned, fill_value=0)
    pol = pol_all.loc[planned]
    base = policy.weeks_of_cover(plan_prof)
    res_pol = simulate.run(prof, pol, test_demand)
    res_base = simulate.run(prof, base, test_demand)

    sweep = []
    for method, settings, make, label in (
            ("Statistical", config.SWEEP_LEVELS, lambda s: policy.statistical(plan_prof, s), lambda s: f"{s:.1%}".replace(".0%", "%")),
            ("Weeks of cover", config.COVER_WEEKS, lambda s: policy.weeks_of_cover(plan_prof, s), lambda s: f"{s} wk")):
        for s in settings:
            r = simulate.summarize(simulate.run(prof, make(s), test_demand), prof).iloc[0]
            sweep.append({"method": method, "setting": s, "label": label(s), **r.to_dict()})
    sweep = pd.DataFrame(sweep)
    needed = {m: float(np.interp(config.COMPARE_FILL_RATE, g["fill_rate"], g["avg_inventory_value"]))
              for m, g in sweep.groupby("method")}

    by_pol = simulate.summarize(res_pol, prof, ["abc"])
    by_base = simulate.summarize(res_base, prof, ["abc"])
    all_pol = simulate.summarize(res_pol, prof).iloc[0]
    all_base = simulate.summarize(res_base, prof).iloc[0]
    by_xyz = simulate.summarize(res_pol, prof, ["xyz"])
    by_cell = simulate.summarize(res_pol, prof, ["abc", "xyz"])
    mat = classify.matrix(prof)

    config.OUTPUT_DIR.mkdir(exist_ok=True)
    prof.join(pol_all).to_csv(config.OUTPUT_DIR / "sku_policy.csv")
    res_pol.join(res_base, lsuffix="_abc_policy", rsuffix="_weeks_of_cover").to_csv(config.OUTPUT_DIR / "backtest_by_sku.csv")
    pd.concat({"ABC policy": by_pol, "Weeks of cover": by_base}).to_csv(config.OUTPUT_DIR / "backtest_by_class.csv")
    by_cell.to_csv(config.OUTPUT_DIR / "backtest_by_abc_xyz.csv")
    sweep.to_csv(config.OUTPUT_DIR / "service_vs_inventory.csv", index=False)

    charts.pareto(prof)
    charts.abc_xyz_heatmap(mat)
    charts.tradeoff(sweep, all_pol, needed)
    charts.class_results(by_pol, by_base)
    ax_skus = plan_prof[(plan_prof["abc"] == "A") & (plan_prof["xyz"] == "X")].sort_values("rank")
    code = ax_skus.index[0]
    one, hist = simulate.run(prof, pol.loc[[code]], test_demand.loc[[code]], keep_history=True)
    charts.sku_example(code, prof.loc[code, "description"], config.TEST_WEEKS, test_demand.loc[code].to_numpy(),
                       hist["on_hand"][0], pol.loc[code, "reorder_point"], pol.loc[code, "safety_stock"])

    workbook.build(WORKBOOK, prof, planned, res_pol, res_base, pol, base, sweep)

    key = {
        "cleaning": steps,
        "skus_2010": len(prof), "skus_planned": len(planned),
        "revenue_2010": round(prof["revenue"].sum(), 2),
        "abc": prof.groupby("abc").agg(skus=("revenue", "size"), share=("revenue_share", "sum")).round(4).to_dict("index"),
        "xyz": prof["xyz"].value_counts().to_dict(),
        "matrix": mat.round(4).to_dict("records"),
        "demand_2011_vs_2010_planned": round(test_demand.sum().sum() / calib.loc[planned].sum().sum(), 4),
        "policy": all_pol.round(4).to_dict(), "weeks_of_cover": all_base.round(4).to_dict(),
        "policy_by_abc": by_pol.round(4).to_dict("index"), "cover_by_abc": by_base.round(4).to_dict("index"),
        "policy_by_xyz": by_xyz[["skus", "fill_rate", "avg_inventory_value"]].round(4).to_dict("index"),
        "policy_by_cell": by_cell[["skus", "fill_rate", "avg_inventory_value"]].round(4).reset_index().to_dict("records"),
        "sweep": sweep[["method", "label", "fill_rate", "avg_inventory_value", "total_cost", "stockout_weeks"]].round(4).to_dict("records"),
        "inventory_for_fill_rate": {"fill_rate": config.COMPARE_FILL_RATE, **{k: round(v) for k, v in needed.items()}},
        "example_sku": {"code": code, "description": prof.loc[code, "description"], **pol.loc[code].round(2).to_dict(),
                        **one.iloc[0].round(4).to_dict(), "mean_weekly": round(prof.loc[code, "mean_weekly"], 1),
                        "sd_weekly": round(prof.loc[code, "sd_weekly"], 1)},
    }
    (config.OUTPUT_DIR / "key_numbers.json").write_text(json.dumps(key, indent=2, default=float))
    print(json.dumps(key, indent=1, default=float))


if __name__ == "__main__":
    main(check_only="--check" in sys.argv)
