import { useState } from "react";
import { auth } from "../../firebase";
import { useTickerSearch } from "../../hooks/useTickerSearch";
import { type IndexSuggestion } from "../APIs/StockFirestore";

interface RiskRewardOptimal {
  leverage: number;
  positionSize: number;
  breachProbability: number;
  expectedValue: number;
  marginRatePct: number;
}

interface PositionSizingResult {
  ticker: string;
  cash: number;
  drawdownToleranceDollars: number;
  confidenceLevelPct: number;
  holdingPeriodYears: number;
  driftLookbackYears: number;
  estimatedAnnualVolatility: number;
  estimatedAnnualDrift: number;
  currentPrice: number;
  maxLeverage: number;
  recommendedPositionSize: number;
  achievedBreachProbability: number;
  riskRewardOptimal: RiskRewardOptimal;
}

const POSITION_SIZING_URL = "https://us-central1-vigila-d6c82.cloudfunctions.net/position_sizing";

const PositionSizingModal = () => {
  const {
    query,
    setQuery,
    suggestions,
    loading,
    error: searchError,
    isFocused,
    setIsFocused,
    clearSearch,
  } = useTickerSearch();

  const [selectedTicker, setSelectedTicker] = useState<IndexSuggestion | null>(null);

  const formatShares = (positionSize: number, price: number): string => {
    const shares = Math.round(positionSize / price);
    return `${shares.toLocaleString()} share${shares === 1 ? "" : "s"} @ $${price.toFixed(2)}/share`;
  };
  const handleSelectTicker = (suggestion: IndexSuggestion) => {
    setSelectedTicker(suggestion);
    clearSearch();
    setIsFocused(false);
  };

  const handleClearTicker = () => {
    setSelectedTicker(null);
  };

  const [cash, setCash] = useState<string>("");
  const [drawdownTolerance, setDrawdownTolerance] = useState<string>("");
  const [confidenceLevel, setConfidenceLevel] = useState<string>("5");
  const [holdingPeriodYears, setHoldingPeriodYears] = useState<string>("1");
  const [driftLookbackYears, setDriftLookbackYears] = useState<string>("5");

  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [result, setResult] = useState<PositionSizingResult | null>(null);

  const canSubmit =
    selectedTicker !== null &&
    cash !== "" &&
    drawdownTolerance !== "" &&
    confidenceLevel !== "" &&
    driftLookbackYears !== "" &&
    Number(cash) > 0 &&
    Number(drawdownTolerance) > 0 &&
    Number(drawdownTolerance) < Number(cash) &&
    Number(confidenceLevel) > 0 &&
    Number(confidenceLevel) < 100 &&
    Number(driftLookbackYears) > 0;

  const handleAnalyze = async () => {
    if (!selectedTicker) return;

    setIsAnalyzing(true);
    setAnalysisError(null);
    setResult(null);

    try {
      const user = auth.currentUser;
      if (!user) {
        throw new Error("You must be logged in to run this analysis.");
      }
      const idToken = await user.getIdToken();

      const positionResponse = await fetch(POSITION_SIZING_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${idToken}`,
        },
        body: JSON.stringify({
          cash: Number(cash),
          drawdownTolerance: Number(drawdownTolerance),
          confidenceLevel: Number(confidenceLevel),
          indexTicker: selectedTicker.symbol,
          holdingPeriodYears: Number(holdingPeriodYears) || 1,
          driftLookbackYears: Number(driftLookbackYears) || 1,
        }),
      });

      const data = await positionResponse.json();

      if (!positionResponse.ok) {
        throw new Error(data.error || `Request failed: ${positionResponse.status}`);
      }

      setResult(data);
    } catch (err: any) {
      setAnalysisError(err.message || "Failed to run analysis. Please try again.");
    } finally {
      setIsAnalyzing(false);
    }
  };

  return (
    <div className="position-relative">
      <label htmlFor="position-sizing-search" className="form-label">
        Search for a Ticker to Analyze
      </label>

      {selectedTicker ? (
        <div className="d-flex align-items-center justify-content-between border rounded p-2 mb-3">
          <div>
            <div className="fw-bold">{selectedTicker.name}</div>
            <small className="text-muted">
              {selectedTicker.symbol} ({selectedTicker.exchange})
            </small>
          </div>
          <button
            type="button"
            className="btn-close"
            aria-label="Clear ticker"
            onClick={handleClearTicker}
          ></button>
        </div>
      ) : (
        <div className="position-relative mb-3">
          <input
            id="position-sizing-search"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onFocus={() => {
              setIsFocused(true);
              setResult(null);
              setAnalysisError(null);
            }}
            onBlur={() => setTimeout(() => setIsFocused(false), 200)}
            placeholder="e.g., SPY"
            className="form-control"
            autoComplete="off"
            style={{ paddingRight: query ? "40px" : "12px" }}
          />
          {query && (
            <button
              type="button"
              onClick={clearSearch}
              aria-label="Clear input"
              className="btn position-absolute top-50 end-0 translate-middle-y text-secondary"
              style={{
                maxWidth: "40px",
                maxHeight: "40px",
                fontSize: "20px",
                lineHeight: "1",
                textDecoration: "none",
              }}
            >
              ×
            </button>
          )}
        </div>
      )}

      {searchError && (
        <div className="text-danger mt-1" style={{ fontSize: "0.875em" }}>
          {searchError}
        </div>
      )}

      {!selectedTicker && isFocused && query.length >= 2 && (
        <div className="list-group position-absolute w-100" style={{ zIndex: 1000 }}>
          {loading ? (
            <div className="list-group-item text-muted p-2">
              <small>Loading...</small>
            </div>
          ) : suggestions ? (
            suggestions.length > 0 ? (
              suggestions.slice(0, 3).map((suggestion) => (
                <div
                  key={suggestion.symbol}
                  className="list-group-item d-flex justify-content-between align-items-center text-start p-2"
                >
                  <div>
                    <div className="fw-bold">{suggestion.name}</div>
                    <small className="text-muted">
                      {suggestion.symbol} ({suggestion.exchange})
                    </small>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      handleSelectTicker(suggestion);
                    }}
                  >
                    Select
                  </button>
                </div>
              ))
            ) : (
              <div className="list-group-item text-muted p-2">
                <small>No results found. Please use the ticker symbol (e.g., SPY) instead of the company name.</small>
              </div>
            )
          ) : null}
        </div>
      )}

      <hr className="my-4" />

      <div className="mb-3">
        <label htmlFor="cash-input" className="form-label">Cash Amount ($)</label>
        <input
          id="cash-input"
          type="number"
          min="0"
          step="any"
          className="form-control"
          value={cash}
          onChange={(e) => setCash(e.target.value)}
          placeholder="e.g., 1500"
        />
      </div>

      <div className="mb-3">
        <label htmlFor="drawdown-input" className="form-label">Max Drawdown Tolerance ($)</label>
        <input
          id="drawdown-input"
          type="number"
          min="0"
          step="any"
          className="form-control"
          value={drawdownTolerance}
          onChange={(e) => setDrawdownTolerance(e.target.value)}
          placeholder="e.g., 200"
        />
      </div>

      <div className="mb-3">
        <label htmlFor="confidence-input" className="form-label">
          Confidence Level (max % chance of breaching drawdown)
        </label>
        <input
          id="confidence-input"
          type="number"
          min="0.1"
          max="99"
          step="0.1"
          className="form-control"
          value={confidenceLevel}
          onChange={(e) => setConfidenceLevel(e.target.value)}
          placeholder="e.g., 1 for 1%"
        />
      </div>

      <div className="mb-3">
        <label htmlFor="holding-period-input" className="form-label">Holding Period (years)</label>
        <input
          id="holding-period-input"
          type="number"
          min="0.1"
          step="0.1"
          className="form-control"
          value={holdingPeriodYears}
          onChange={(e) => setHoldingPeriodYears(e.target.value)}
          placeholder="e.g., 1"
        />
      </div>

      <div className="mb-3">
        <label htmlFor="drift-lookback-input" className="form-label">
          Drift Lookback Period (years)
        </label>
        <input
          id="drift-lookback-input"
          type="number"
          min="0.1"
          step="0.1"
          className="form-control"
          value={driftLookbackYears}
          onChange={(e) => setDriftLookbackYears(e.target.value)}
          placeholder="e.g., 1"
        />
        <small className="text-muted">
          How far back to look when estimating expected return. Shorter windows
          (e.g. 1 year) are noisier and more sensitive to recent performance;
          longer windows (e.g. 5-10 years) are more stable but slower to react.
        </small>
      </div>

      {analysisError && (
        <div className="text-danger mb-3" style={{ fontSize: "0.875em" }}>
          {analysisError}
        </div>
      )}

      <div className="d-flex justify-content-center">
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleAnalyze}
          disabled={!canSubmit || isAnalyzing}
        >
          {isAnalyzing ? "Analyzing..." : "Run Position Sizing Analysis"}
        </button>
      </div>

      {result && (
        <div className="mt-4 p-3 border rounded bg-light">
          <h6 className="mb-3">Results for {result.ticker}</h6>
          
          <div className="d-flex flex-column gap-2" style={{ fontSize: "0.9em" }}>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Adjusted Position Size:</span>
              <div className="text-end">
                <span className="fw-bold">
                  ${result.recommendedPositionSize.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <div>
                  <small className="text-muted">
                    {formatShares(result.recommendedPositionSize, result.currentPrice)}
                  </small>
                </div>
              </div>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Max Leverage:</span>
              <span className="fw-bold">{result.maxLeverage.toFixed(3)}x</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Estimated Annual Volatility:</span>
              <span>{(result.estimatedAnnualVolatility * 100).toFixed(2)}%</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Estimated Annual Drift:</span>
              <span>{(result.estimatedAnnualDrift * 100).toFixed(2)}%</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Drift Lookback Used:</span>
              <span>{result.driftLookbackYears} yr</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Achieved Breach Probability:</span>
              <span>{(result.achievedBreachProbability * 100).toFixed(2)}%</span>
            </div>
          </div>

          <hr />
          <h6 className="mb-3">Risk-Reward Optimized Alternative</h6>
          <p className="text-muted" style={{ fontSize: "0.85em" }}>
            This alternative maximizes expected profit after simple margin interest while
            penalizing potential drawdowns by their breach probability, so it may
            recommend a different leverage than the confidence-based approach.
          </p>
          <div className="d-flex flex-column gap-2" style={{ fontSize: "0.9em" }}>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Recommended Position Size:</span>
              <div className="text-end">
                <span className="fw-bold">
                  ${result.riskRewardOptimal.positionSize.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </span>
                <div>
                  <small className="text-muted">
                    {formatShares(result.riskRewardOptimal.positionSize, result.currentPrice)}
                  </small>
                </div>
              </div>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Recommended Leverage:</span>
              <span className="fw-bold">{result.riskRewardOptimal.leverage.toFixed(3)}x</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Margin Interest Rate:</span>
              <span>{result.riskRewardOptimal.marginRatePct.toFixed(3)}%</span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Expected Net Profit:</span>
              <span>
                ${result.riskRewardOptimal.expectedValue.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="text-muted">Implied Breach Probability:</span>
              <span>{(result.riskRewardOptimal.breachProbability * 100).toFixed(2)}%</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PositionSizingModal;