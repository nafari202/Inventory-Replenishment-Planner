"""Static charts for the README."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.ticker import FuncFormatter, PercentFormatter  # noqa: E402

from . import config  # noqa: E402

# Same palette and type as the Pool Point Network Planner charts
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#fcfcfb"
CRITICAL = "#d03b3b"
BLUE_LIGHT = "#cde2fb"
BLUES = LinearSegmentedColormap.from_list("blues", ["#f0efec", "#86b6ef", "#184f95"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": ["Segoe UI", "DejaVu Sans", "sans-serif"], "font.size": 10,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "legend.frameon": False, "legend.labelcolor": INK_2, "lines.linewidth": 2,
})

pounds_k = FuncFormatter(lambda v, _: f"£{v / 1000:,.0f}K")


def _save(fig, name):
    path = config.IMAGE_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=INK_2, fontsize=9, va="bottom")


def pareto(prof: pd.DataFrame):
    prof = prof.sort_values("rank")
    x = prof["rank"] / len(prof)
    y = prof["cum_share"]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(x, y, color=BLUE)
    n_a = (prof["abc"] == "A").sum()
    n_b = (prof["abc"] == "B").sum()
    edges = [0, n_a / len(prof), (n_a + n_b) / len(prof), 1]
    for (lo, hi), label in zip(zip(edges[:-1], edges[1:]), "ABC"):
        ax.axvspan(lo, hi, color=BLUE_LIGHT if label == "A" else SURFACE, alpha=0.6 if label == "A" else 0, lw=0)
        skus = (prof["abc"] == label).sum()
        rev = prof.loc[prof["abc"] == label, "revenue_share"].sum()
        ax.text((lo + hi) / 2, 0.08, f"{label}\n{skus:,} SKUs\n{rev:.0%} of revenue", ha="center", va="bottom",
                color=INK_2, fontsize=9)
    for e in edges[1:-1]:
        ax.axvline(e, color=AXIS, lw=1)
    ax.xaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Share of SKUs, ranked by 2010 revenue")
    ax.set_title("A few SKUs carry most of the revenue", pad=22)
    _subtitle(ax, f"Cumulative share of 2010 revenue across {len(prof):,} SKUs")
    return _save(fig, "01_abc_pareto.png")


def abc_xyz_heatmap(mat: pd.DataFrame):
    share = mat.pivot(index="abc", columns="xyz", values="revenue_share").reindex(index=list("ABC"), columns=list("XYZ")).fillna(0)
    skus = mat.pivot(index="abc", columns="xyz", values="skus").reindex(index=list("ABC"), columns=list("XYZ")).fillna(0)
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.imshow(share.to_numpy(), cmap=BLUES, vmin=0, vmax=share.to_numpy().max())
    ax.grid(False)
    for i, a in enumerate("ABC"):
        for j, x in enumerate("XYZ"):
            v = share.loc[a, x]
            color = "white" if v > share.to_numpy().max() * 0.55 else INK
            ax.text(j, i, f"{int(skus.loc[a, x]):,} SKUs\n{v:.1%} of revenue", ha="center", va="center", color=color, fontsize=9.5)
    ax.set_xticks(range(3), ["X  steady\n(CV ≤ 0.5)", "Y  variable\n(0.5–1.0)", "Z  erratic\n(CV > 1.0)"])
    ax.set_yticks(range(3), ["A  top 80%", "B  next 15%", "C  last 5%"])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("ABC-XYZ matrix", pad=22)
    _subtitle(ax, "Revenue class (rows) by variability of weekly demand (columns), 2010")
    return _save(fig, "02_abc_xyz_matrix.png")


def tradeoff(sweep: pd.DataFrame, policy_point: pd.Series, needed: dict):
    fig, ax = plt.subplots(figsize=(10, 5.2))
    styles = {"Statistical": (BLUE, "o", (-7, 6)), "Weeks of cover": (MUTED, "s", (7, -13))}
    for method, g in sweep.groupby("method"):
        color, marker, offset = styles[method]
        ax.plot(g["avg_inventory_value"], g["fill_rate"], color=color, marker=marker, ms=4,
                label="Safety stock from demand variability (service target)" if method == "Statistical"
                else "Safety stock as weeks of average demand")
        for _, r in g.iterrows():
            ax.annotate(r["label"], (r["avg_inventory_value"], r["fill_rate"]), xytext=offset, textcoords="offset points",
                        color=color, fontsize=8, ha="left" if offset[0] > 0 else "right")
    target = config.COMPARE_FILL_RATE
    ax.axhline(target, color=AXIS, lw=1, ls="--")
    lo, hi = needed["Statistical"], needed["Weeks of cover"]
    ax.annotate("", xy=(hi, target), xytext=(lo, target), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.annotate(f"£{(hi - lo) / 1000:,.0f}K less inventory\nfor a {target:.0%} fill rate", xy=((lo + hi) / 2, target),
                xytext=(hi + 30000, target - 0.007), ha="left", va="top", fontsize=9, color=INK, fontweight="bold",
                arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    ax.scatter([policy_point["avg_inventory_value"]], [policy_point["fill_rate"]], color=ORANGE, s=70, zorder=5)
    ax.annotate("ABC targets 98 / 95 / 90%", (policy_point["avg_inventory_value"], policy_point["fill_rate"]),
                xytext=(-12, 10), textcoords="offset points", ha="right", color=ORANGE, fontsize=9, fontweight="bold")
    ax.xaxis.set_major_formatter(pounds_k)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xlabel("Average inventory value at cost, Jan–Nov 2011")
    ax.set_ylabel("Fill rate (share of sales value shipped)")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title("Sizing safety stock by variability buys more service per pound", pad=22)
    _subtitle(ax, "Backtest on 2011 demand. Both methods order the same EOQ quantities; only safety stock differs.")
    return _save(fig, "03_service_vs_inventory.png")


def class_results(policy: pd.DataFrame, base: pd.DataFrame):
    classes = list("ABC")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), gridspec_kw={"wspace": 0.3})
    x = np.arange(3)
    w = 0.38
    ax = axes[0]
    ax.bar(x - w / 2, base.loc[classes, "fill_rate"], w, color=AXIS, label=f"Weeks of cover ({config.BASELINE_COVER_WEEKS} wk)")
    ax.bar(x + w / 2, policy.loc[classes, "fill_rate"], w, color=BLUE, label="ABC policy")
    for i, c in enumerate(classes):
        ax.text(i - w / 2, base.loc[c, "fill_rate"] + 0.005, f"{base.loc[c, 'fill_rate']:.1%}", ha="center", fontsize=8, color=INK_2)
        ax.text(i + w / 2, policy.loc[c, "fill_rate"] + 0.005, f"{policy.loc[c, 'fill_rate']:.1%}", ha="center", fontsize=8, color=INK_2)
    lo = min(base["fill_rate"].min(), policy["fill_rate"].min())
    ax.set_ylim(max(0, lo - 0.08), 1.0)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_xticks(x, [f"Class {c}" for c in classes])
    ax.set_title("Fill rate", pad=8)
    ax.legend(loc="upper right", fontsize=8)
    ax = axes[1]
    ax.bar(x - w / 2, base.loc[classes, "avg_inventory_value"], w, color=AXIS)
    ax.bar(x + w / 2, policy.loc[classes, "avg_inventory_value"], w, color=BLUE)
    ax.yaxis.set_major_formatter(pounds_k)
    ax.set_xticks(x, [f"Class {c}" for c in classes])
    ax.set_title("Average inventory value", pad=8)
    fig.suptitle(f"ABC policy vs {config.BASELINE_COVER_WEEKS} weeks of cover, by class", x=0.125, y=1.06, ha="left",
                 fontweight="bold", fontsize=12, color=INK)
    fig.text(0.125, 0.985, "2011 backtest. Both policies hold about the same total inventory.", ha="left", fontsize=9, color=INK_2)
    return _save(fig, "04_policy_by_class.png")


def sku_example(code: str, desc: str, weeks: pd.DatetimeIndex, demand: np.ndarray, on_hand: np.ndarray, rop: float, ss: float):
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.bar(weeks, demand, width=5, color=BLUE_LIGHT, label="Weekly demand")
    ax.step(weeks, on_hand, where="post", color=BLUE, label="On hand at week end")
    ax.axhline(rop, color=ORANGE, lw=1.4, ls="--", label=f"Reorder point ({rop:,.0f})")
    ax.axhline(ss, color=MUTED, lw=1.2, ls=":", label=f"Safety stock ({ss:,.0f})")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("Units")
    ax.legend(loc="upper left", ncol=4, fontsize=8, bbox_to_anchor=(0, -0.1))
    ax.set_title(f"{desc.title()} ({code}) under the ABC policy", pad=22)
    _subtitle(ax, "Each drop is a week of demand; each jump is an order arriving two weeks after it was placed.")
    return _save(fig, "05_sku_example.png")
