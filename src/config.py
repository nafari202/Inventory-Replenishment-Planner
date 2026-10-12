"""Planning assumptions and paths. Change a number here and rerun run_pipeline.py."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
IMAGE_DIR = ROOT / "images"

# Calendar 2010 sets the policy; Jan-Nov 2011 tests it on demand the policy has never seen.
# The week of Dec 5, 2011 is left out because the data stops on Friday, Dec 9.
CALIBRATION_WEEKS = pd.date_range("2010-01-04", "2010-12-27", freq="W-MON")  # 52 weeks
TEST_WEEKS = pd.date_range("2011-01-03", "2011-11-28", freq="W-MON")  # 48 weeks

# ABC by share of 2010 revenue; XYZ by coefficient of variation (CV) of weekly demand.
# Textbook XYZ cutoffs (0.5 / 1.0) assume monthly demand. Weekly wholesale demand is far lumpier
# (median CV 2.2), and those cutoffs would put 91% of SKUs in Z, so the cutoffs are 1.0 and 2.0.
ABC_CUTOFFS = {"A": 0.80, "B": 0.95}  # cumulative revenue share; the rest is C
XYZ_CUTOFFS = {"X": 1.0, "Y": 2.0}  # CV at or below; the rest is Z

# Cycle service level targets by ABC class (chance of not running out in a replenishment cycle).
SERVICE_TARGETS = {"A": 0.98, "B": 0.95, "C": 0.90}

LEAD_TIME_WEEKS = 2  # supplier lead time, assumed
ORDER_COST = 25.0  # GBP per purchase order line, assumed
HOLDING_RATE = 0.25  # annual holding cost as a share of unit cost, assumed
COST_RATIO = 0.60  # unit cost as a share of average selling price (40% gross margin), assumed
WEEKS_PER_YEAR = 52

# Rule of thumb the statistical policy is compared against: the same safety stock in weeks of
# average demand for every SKU. Both policies order the same EOQ quantities, so the comparison
# isolates how safety stock is set. 4 weeks holds about the same inventory as the ABC policy.
BASELINE_COVER_WEEKS = 4

# Trade-off curves: one service level for every SKU, and a range of weeks of cover.
SWEEP_LEVELS = [0.50, 0.70, 0.80, 0.90, 0.95, 0.98, 0.99, 0.995]
COVER_WEEKS = [0, 1, 2, 3, 4, 6, 8]
COMPARE_FILL_RATE = 0.95  # inventory each method needs to reach this fill rate
