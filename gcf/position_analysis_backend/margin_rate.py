from io import StringIO
import pandas as pd
import requests

FRED_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FED_FUNDS_UPPER_SERIES = "DFEDTARU"

DEFAULT_ANNUALIZED_MARGIN_RATE = 0.05


def get_annualized_margin_rate(timeout: float = 30.0) -> float:
    """
    Return the current upper bound of the Fed Funds Target Range as a
    decimal annualized rate (e.g. 5.50% -> 0.055), pulled from FRED.

    Falls back to `default` if the request fails, times out, or the
    series has no valid (non-missing) observations.
    """
    try:
        resp = requests.get(
            FRED_CSV_URL,
            params={"id": FED_FUNDS_UPPER_SERIES},
            timeout=timeout,
        )
        resp.raise_for_status()

        df = pd.read_csv(StringIO(resp.text))
        # FRED's CSV has two columns: observation_date, <series_id>
        df = df.rename(columns={df.columns[0]: "date", df.columns[1]: "value"})
        df["value"] = pd.to_numeric(df["value"], errors="coerce")  # "." -> NaN
        df = df.dropna(subset=["value"])

        if df.empty:
            raise ValueError(f"{FED_FUNDS_UPPER_SERIES} returned no valid observations")

        latest_pct = float(df["value"].iloc[-1])
        return latest_pct / 100.0

    except Exception as e:
        print(
            f"WARNING: could not fetch fed funds upper bound from FRED, "
            f"falling back to default {DEFAULT_ANNUALIZED_MARGIN_RATE}: {type(e).__name__}: {e}"
        )
        return DEFAULT_ANNUALIZED_MARGIN_RATE


if __name__ == "__main__":
    print("Fetching fed funds upper bound from FRED...")
    rate = get_annualized_margin_rate()
    print(f"Rate: {rate:.4f} ({rate * 100:.2f}%)")

    print("\nSimulating a fetch failure (bad URL) to confirm fallback works...")
    real_url = FRED_CSV_URL
    globals()["FRED_CSV_URL"] = "https://fred.stlouisfed.org/graph/does-not-exist.csv"
    fallback_rate = get_annualized_margin_rate()
    globals()["FRED_CSV_URL"] = real_url
    print(f"Fallback rate (expect {DEFAULT_ANNUALIZED_MARGIN_RATE}): {fallback_rate}")