import functions_framework
from firebase_admin import auth, initialize_app
from flask import jsonify
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
import yfinance as yf
from datetime import datetime, timedelta, timezone

initialize_app()


# ---------- Market data ----------

def get_vol_and_drift(ticker: str, lookback_days: int = 252):
    """
    Pull historical daily prices and compute annualized log-return
    volatility and arithmetic drift for the given ticker.
    """
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(lookback_days * 1.6))  # buffer for weekends/holidays

    df = yf.download(ticker, start=start, end=end, interval="1d",
                      progress=False, auto_adjust=True)
    if df.empty or len(df) < 30:
        raise ValueError(f"Not enough price history for ticker '{ticker}'")

    close = df["Close"].dropna().squeeze()
    log_returns = np.log(close / close.shift(1)).dropna()

    sigma_annual = float(log_returns.std() * np.sqrt(252))
    simple_returns = close.pct_change().dropna()
    mu_arith_annual = float(simple_returns.mean() * 252)

    return sigma_annual, mu_arith_annual


# ---------- GBM barrier-breach math ----------

def breach_prob_gbm(S0, B, T, mu_log, sigma):
    """
    Probability that GBM starting at S0 ever falls to or below barrier B
    within time T (continuous monitoring), via the reflection principle.
    """
    if B >= S0:
        return 1.0  # already at/past barrier
    d1 = (np.log(B / S0) - mu_log * T) / (sigma * np.sqrt(T))
    d2 = (np.log(B / S0) + mu_log * T) / (sigma * np.sqrt(T))
    term1 = norm.cdf(d1)
    term2 = (B / S0) ** (2 * mu_log / sigma ** 2) * norm.cdf(d2)
    return term1 + term2


def solve_max_leverage(cash, drawdown_dollars, alpha, sigma, mu_arith, T=1.0):
    """
    Find the maximum leverage L such that breach probability == alpha.
    Returns (max_leverage, achieved_breach_probability).
    """
    B = cash - drawdown_dollars
    if B <= 0:
        raise ValueError("Drawdown tolerance must be less than cash amount")

    def f(leverage):
        lev_sigma = sigma * leverage
        lev_mu_arith = mu_arith * leverage
        lev_mu_log = lev_mu_arith - 0.5 * lev_sigma ** 2
        return breach_prob_gbm(cash, B, T, lev_mu_log, lev_sigma) - alpha

    lo, hi = 1e-4, 50.0

    if f(lo) > 0:
        # even near-zero leverage already exceeds alpha -> no leverage is safe enough
        return 0.0, f(lo) + alpha

    if f(hi) < 0:
        # even 50x doesn't reach alpha -> cap at hi
        return hi, f(hi) + alpha

    max_leverage = brentq(f, lo, hi, xtol=1e-4)
    achieved_breach_prob = f(max_leverage) + alpha
    return max_leverage, achieved_breach_prob


# ---------- HTTP entrypoint ----------

@functions_framework.http
def position_sizing(request):
    # CORS preflight
    if request.method == "OPTIONS":
        headers = {
            "Access-Control-Allow-Origin": "https://vigila-d6c82.web.app",
            "Access-Control-Allow-Methods": "POST",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
            "Access-Control-Max-Age": "3600",
        }
        return ("", 204, headers)

    cors_headers = {"Access-Control-Allow-Origin": "https://vigila-d6c82.web.app"}

    # 1. Verify Firebase auth token
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or malformed Authorization header"}), 401, cors_headers

    id_token = auth_header.split("Bearer ")[1]
    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token["uid"]
    except Exception as e:
        print(f"TOKEN VERIFICATION FAILED: {type(e).__name__}: {e}")
        return jsonify({"error": "Invalid or expired token"}), 401, cors_headers

    # 2. Parse and validate input
    data = request.get_json(silent=True) or {}
    cash = data.get("cash")
    drawdown_dollars = data.get("drawdownTolerance")
    confidence_pct = data.get("confidenceLevel")  # e.g. 1-5, meaning 1%-5%
    ticker = data.get("indexTicker", "SPY")
    holding_period_years = float(data.get("holdingPeriodYears", 1.0))

    if cash is None or drawdown_dollars is None or confidence_pct is None:
        return jsonify({"error": "Missing required fields: cash, drawdownTolerance, confidenceLevel"}), 400, cors_headers

    try:
        cash = float(cash)
        drawdown_dollars = float(drawdown_dollars)
        alpha = float(confidence_pct) / 100.0  # convert "1-5 percent" input to 0.01-0.05
    except (TypeError, ValueError):
        return jsonify({"error": "cash, drawdownTolerance, confidenceLevel must be numeric"}), 400, cors_headers

    if cash <= 0 or drawdown_dollars <= 0 or drawdown_dollars >= cash:
        return jsonify({"error": "Invalid cash/drawdown values"}), 400, cors_headers
    if not (0 < alpha < 1):
        return jsonify({"error": "confidenceLevel must be between 0 and 100 (as a percent)"}), 400, cors_headers

    # 3. Fetch market data for the requested index/ticker
    try:
        sigma, mu_arith = get_vol_and_drift(ticker)
    except Exception as e:
        return jsonify({"error": f"Could not fetch data for ticker '{ticker}': {str(e)}"}), 400, cors_headers

    # 4. Solve for max leverage at the target confidence level
    try:
        max_leverage, achieved_prob = solve_max_leverage(
            cash, drawdown_dollars, alpha, sigma, mu_arith, T=holding_period_years
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400, cors_headers

    position_size = max_leverage * cash

    response = {
        "ticker": ticker,
        "cash": cash,
        "drawdownToleranceDollars": drawdown_dollars,
        "confidenceLevelPct": confidence_pct,
        "holdingPeriodYears": holding_period_years,
        "estimatedAnnualVolatility": round(sigma, 4),
        "estimatedAnnualDrift": round(mu_arith, 4),
        "maxLeverage": round(max_leverage, 3),
        "recommendedPositionSize": round(position_size, 2),
        "achievedBreachProbability": round(achieved_prob, 4),
        "modelCaveat": (
            "Based on GBM/reflection-principle model with constant volatility "
            "and drift assumptions, with drift estimated from trailing 1-year "
            "returns. Real markets have fat tails, volatility clustering, and "
            "drift that varies a lot depending on the lookback window, so "
            "actual breach probability may be higher than this estimate, "
            "especially at higher leverage."
        ),
    }
    return jsonify(response), 200, cors_headers