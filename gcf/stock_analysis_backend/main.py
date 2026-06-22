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
    last_price = float(close.iloc[-1])

    return sigma_annual, mu_arith_annual, last_price


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


# ---------- Buy-and-forget leverage model ----------
#
# These functions model a FIXED, non-rebalanced leveraged position: you
# borrow once to buy `cash * leverage` worth of the underlying, and never
# adjust that exposure again. The underlying asset itself still follows its
# own *unleveraged* GBM (mu_arith, sigma unchanged) -- what leverage does is
# translate the equity drawdown barrier into a different price level on that
# same unleveraged path, since your fixed debt amplifies/dampens how price
# moves translate into equity moves. This is different from a continuously
# rebalanced position (e.g. a leveraged ETF), where the position itself
# would be modeled as its own GBM with rescaled drift/vol.

def _breach_position_value(cash, drawdown_dollars, leverage):
    """
    Translate the equity drawdown barrier into the underlying position-value
    level at which that barrier is hit, given a fixed (never rebalanced)
    leveraged position opened at `cash * leverage`.

    Below leverage = drawdown_dollars / cash, the implied breach position
    value is <= 0, meaning the position cannot actually lose enough to hit
    the barrier at that leverage (the fixed debt is too small relative to
    the cushion). Callers should not evaluate breach_prob_gbm in that
    region; this is handled by clamping the leverage search bounds.
    """
    target_equity = cash - drawdown_dollars
    initial_position_value = cash * leverage
    fixed_debt = initial_position_value - cash
    breach_position_value = target_equity + fixed_debt
    return initial_position_value, breach_position_value


def _min_leverage_for_breach_possible(cash, drawdown_dollars):
    """
    The leverage below which breach_position_value <= 0 (barrier
    unreachable under the fixed-debt model). Adding a small epsilon keeps
    us strictly on the valid side for log() in breach_prob_gbm.
    """
    return drawdown_dollars / cash + 1e-6


def solve_max_leverage(cash, drawdown_dollars, alpha, sigma, mu_arith, T=1.0):
    """
    Find the maximum leverage L such that breach probability == alpha,
    under the buy-and-forget (non-rebalanced) leverage model.
    Returns (max_leverage, achieved_breach_probability).
    """
    target_equity = cash - drawdown_dollars
    if target_equity <= 0:
        raise ValueError("Drawdown tolerance must be less than cash amount")

    # The underlying asset's own drift/vol are unleveraged -- leverage only
    # shows up in how the barrier translates, not in sigma or mu_log here.
    asset_mu_log = mu_arith - 0.5 * sigma ** 2

    def f(leverage):
        initial_position_value, breach_position_value = _breach_position_value(
            cash, drawdown_dollars, leverage
        )
        return breach_prob_gbm(
            initial_position_value, breach_position_value, T, asset_mu_log, sigma
        ) - alpha

    lo = max(1e-4, _min_leverage_for_breach_possible(cash, drawdown_dollars))
    hi = 50.0

    if f(lo) > 0:
        # even near-zero leverage already exceeds alpha -> no leverage is safe enough
        return 0.0, f(lo) + alpha

    if f(hi) < 0:
        # even 50x doesn't reach alpha -> cap at hi
        return hi, f(hi) + alpha

    max_leverage = brentq(f, lo, hi, xtol=1e-4)
    achieved_breach_prob = f(max_leverage) + alpha
    return max_leverage, achieved_breach_prob

def expected_profit(cash, mu_arith, leverage, T):
    return cash * leverage * (np.exp(mu_arith * T) - 1)


def risk_reward_objective(leverage, cash, drawdown_dollars, sigma, mu_arith, T):
    """
    Expected profit minus a leverage^2-scaled penalty weighted by breach
    probability, under the buy-and-forget leverage model.
    """
    asset_mu_log = mu_arith - 0.5 * sigma ** 2
    initial_position_value, breach_position_value = _breach_position_value(
        cash, drawdown_dollars, leverage
    )
    p_breach = breach_prob_gbm(
        initial_position_value, breach_position_value, T, asset_mu_log, sigma
    )
    profit = expected_profit(cash, mu_arith, leverage, T)

    # penalty scales with leverage^2, so it overtakes profit even once
    penalty = drawdown_dollars * (leverage ** 2) * p_breach
    return profit - penalty


def solve_optimal_leverage(cash, drawdown_dollars, sigma, mu_arith, T=1.0):
    """
    Find the leverage that maximizes expected_profit - drawdown_dollars * P(breach),
    under the buy-and-forget leverage model.
    Returns (optimal_leverage, optimal_expected_value, breach_prob_at_optimum).
    """
    from scipy.optimize import minimize_scalar

    def neg_objective(leverage):
        return -risk_reward_objective(leverage, cash, drawdown_dollars, sigma, mu_arith, T)

    lo = max(1e-4, _min_leverage_for_breach_possible(cash, drawdown_dollars))
    result = minimize_scalar(neg_objective, bounds=(lo, 50.0), method="bounded")
    optimal_leverage = float(result.x)
    optimal_value = float(-result.fun)

    asset_mu_log = mu_arith - 0.5 * sigma ** 2
    initial_position_value, breach_position_value = _breach_position_value(
        cash, drawdown_dollars, optimal_leverage
    )
    p_breach_at_optimum = breach_prob_gbm(
        initial_position_value, breach_position_value, T, asset_mu_log, sigma
    )

    return optimal_leverage, optimal_value, float(p_breach_at_optimum)


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
    drift_lookback_years = float(data.get("driftLookbackYears", 1.0))

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
        lookback_days = int(round(drift_lookback_years * 252))
        sigma, mu_arith, current_price = get_vol_and_drift(ticker, lookback_days=lookback_days)
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

    # 5. Also compute the risk-reward optimal leverage as a secondary recommendation
    optimal_leverage, optimal_expected_value, optimal_breach_prob = solve_optimal_leverage(
        cash, drawdown_dollars, sigma, mu_arith, T=holding_period_years
    )
    optimal_position_size = optimal_leverage * cash

    response = {
        "ticker": ticker,
        "cash": cash,
        "drawdownToleranceDollars": drawdown_dollars,
        "confidenceLevelPct": confidence_pct,
        "holdingPeriodYears": holding_period_years,
        "driftLookbackYears": drift_lookback_years,
        "estimatedAnnualVolatility": round(sigma, 4),
        "estimatedAnnualDrift": round(mu_arith, 4),
        "currentPrice": round(current_price, 2),
        "maxLeverage": round(max_leverage, 3),
        "recommendedPositionSize": round(position_size, 2),
        "achievedBreachProbability": round(achieved_prob, 4),
        "riskRewardOptimal": {
            "leverage": round(optimal_leverage, 3),
            "positionSize": round(optimal_position_size, 2),
            "breachProbability": round(optimal_breach_prob, 4),
            "expectedValue": round(optimal_expected_value, 2),
        },
    }
    return jsonify(response), 200, cors_headers