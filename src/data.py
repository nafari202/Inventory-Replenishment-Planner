"""Load and clean the UCI Online Retail II transactions."""
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_XLSX = ROOT / "data" / "raw" / "online_retail_II.xlsx"
CACHE = ROOT / "data" / "processed" / "transactions.pkl"
SOURCE_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"


def download():
    """Fetch the dataset from the UCI Machine Learning Repository (about 45 MB)."""
    RAW_XLSX.parent.mkdir(parents=True, exist_ok=True)
    zip_path = RAW_XLSX.parent / "online_retail_ii.zip"
    urllib.request.urlretrieve(SOURCE_URL, zip_path)
    with zipfile.ZipFile(zip_path) as z:
        z.extract(RAW_XLSX.name, RAW_XLSX.parent)

# Real products use a 5-digit code with an optional letter suffix (e.g. 85123A).
# Everything else is postage, fees, manual adjustments or gift vouchers.
PRODUCT_CODE = r"^\d{5}[A-Za-z]{0,2}$"


def load_raw() -> pd.DataFrame:
    """Read both sheets of the workbook once, then reuse a pickle cache."""
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    if not RAW_XLSX.exists():
        download()
    # calamine reads the 1M-row workbook in under a minute; the default openpyxl reader takes over an hour
    sheets = pd.read_excel(RAW_XLSX, sheet_name=None, dtype={"Invoice": str, "StockCode": str}, engine="calamine")
    df = pd.concat(sheets.values(), ignore_index=True)
    df = df.rename(columns={"Customer ID": "CustomerID"})
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(CACHE)
    return df


def _cancelled_sales(df: pd.DataFrame) -> pd.Index:
    """Sale rows reversed in full by a later cancellation: same customer, SKU and quantity within 30 days."""
    cancels = df[df["Invoice"].str.startswith("C") & (df["Quantity"] < 0) & df["CustomerID"].notna()]
    cancels = cancels.assign(Quantity=-cancels["Quantity"])[["CustomerID", "StockCode", "Quantity", "InvoiceDate"]]
    sales = df[~df["Invoice"].str.startswith("C") & (df["Quantity"] > 0) & df["CustomerID"].notna()]
    m = sales.reset_index().merge(cancels, on=["CustomerID", "StockCode", "Quantity"], suffixes=("", "_cancel"))
    lag = m["InvoiceDate_cancel"] - m["InvoiceDate"]
    m = m[(lag >= pd.Timedelta(0)) & (lag <= pd.Timedelta(days=30))]
    return pd.Index(m["index"].unique())


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep completed sales of real products. Returns the rows and a step-by-step row count."""
    steps = {"raw rows": len(df)}
    df = df.drop(index=_cancelled_sales(df))
    df = df[~df["Invoice"].str.startswith("C")]
    steps["after removing cancellations and the sales they reversed"] = len(df)
    df = df[(df["Quantity"] > 0) & (df["Price"] > 0)]
    steps["after removing zero or negative quantity/price"] = len(df)
    df = df[df["StockCode"].str.match(PRODUCT_CODE)]
    steps["after removing postage, fees and vouchers"] = len(df)
    df = df.drop_duplicates()
    steps["after removing duplicate rows"] = len(df)
    df = df.assign(
        StockCode=df["StockCode"].str.upper(),
        Revenue=df["Quantity"] * df["Price"],
        Week=df["InvoiceDate"].dt.to_period("W-SUN").dt.start_time,
    )
    return df, steps
