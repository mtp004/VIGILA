import { useState, useEffect, useMemo } from "react";
import debounce from "lodash/debounce";
import { addVolumeSymbols, type IndexSuggestion} from "../APIs/Firestore";

interface VolumeModalProps {
  onAddSuccess: () => void; // callback to notify parent
}

const VolumeModal = ({ onAddSuccess }: VolumeModalProps) => {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<IndexSuggestion[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const [selectedSymbols, setSelectedSymbols] = useState<IndexSuggestion[]>([]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const API_KEY = import.meta.env.VITE_FINANCE_API_KEY;

  const fetchIndexData = async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setSuggestions([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(
        `https://financialmodelingprep.com/stable/search-symbol?query=${searchQuery}&apikey=${API_KEY}`
      );

      if (!response.ok) {
        throw new Error(
          "Network response was not ok. API key might be invalid or limit exceeded."
        );
      }

      const data: IndexSuggestion[] = await response.json();
      setSuggestions(data);
    } catch (err: any) {
      setError(
        "Failed to fetch data. Please check your API key and network connection."
      );
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const debouncedFetch = useMemo(() => debounce(fetchIndexData, 400), []);

  useEffect(() => {
    debouncedFetch(query);
    return () => debouncedFetch.cancel();
  }, [query, debouncedFetch]);

  const handleAddSymbol = (suggestion: IndexSuggestion) => {
    if (!selectedSymbols.some((s) => s.symbol === suggestion.symbol)) {
      setSelectedSymbols((prev) => [...prev, suggestion]);
    }
    setQuery("");
    setSuggestions([]);
    setIsFocused(true);
  };

  const handleRemoveSymbolLocal = (symbol: string) => {
    setSelectedSymbols((prev) => prev.filter((s) => s.symbol !== symbol));
  };

  const handleAddVolumeIndicator = async () => {
    if (selectedSymbols.length === 0) return;

    setIsSaving(true);
    setSaveError(null);
    setSaveSuccess(false);

    try {
        // Pass the full IndexSuggestion objects instead of just the symbols
        await addVolumeSymbols(selectedSymbols);
        setSaveSuccess(true);
        setSelectedSymbols([]);

        // Notify parent to reload list
        onAddSuccess();
    } catch (err: any) {
        setSaveError(err.message || "Failed to save symbols. Please try again.");
        setSaveSuccess(false);
    } finally {
        setIsSaving(false);
    }
  };

  return (
    <div className="position-relative">
      {/* Search Input */}
      <label htmlFor="index-search" className="form-label">
        Search for a Financial Symbol
      </label>
      <input
        id="index-search"
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onFocus={() => {
          setIsFocused(true);
          setSaveSuccess(false);
          setSaveError(null);
        }}
        onBlur={() => setTimeout(() => setIsFocused(false), 200)}
        placeholder="e.g., AAPL or Apple"
        className="form-control mb-3"
        autoComplete="off"
      />

      {loading && <div className="form-text">Loading...</div>}
      {error && (
        <div className="text-danger mt-1" style={{ fontSize: "0.875em" }}>
          {error}
        </div>
      )}

      {/* Suggestions List */}
      {isFocused && suggestions.length > 0 && (
        <div
          className="list-group position-absolute w-100"
          style={{ zIndex: 1000 }}
        >
          {suggestions.slice(0, 3).map((suggestion) => (
            <div
              key={suggestion.symbol}
              className="list-group-item list-group-item-action d-flex justify-content-between align-items-center text-start p-2"
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
                  handleAddSymbol(suggestion);
                }}
              >
                +
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Selected Symbols */}
      <div className="mt-4">
        <h6 className="mb-2">Selected Symbols ({selectedSymbols.length})</h6>
        <div className="d-flex flex-wrap gap-2">
          {selectedSymbols.map((symbol) => (
            <span
              key={symbol.symbol}
              className="badge bg-primary d-flex align-items-center p-2"
            >
              {symbol.symbol}
              <button
                type="button"
                className="btn-close btn-close-white ms-2"
                aria-label="Remove"
                onClick={() => handleRemoveSymbolLocal(symbol.symbol)}
              ></button>
            </span>
          ))}
        </div>
      </div>

      <hr className="my-4" />

      {/* Save Button */}
      <div className="d-flex flex-column justify-content-center align-items-center">
        {saveError && (
          <div className="text-danger me-3" style={{ fontSize: "0.875em" }}>
            {saveError}
          </div>
        )}
        {saveSuccess && (
          <div className="text-success me-3" style={{ fontSize: "0.875em" }}>
            ✅ Symbols added successfully!
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleAddVolumeIndicator}
          disabled={selectedSymbols.length === 0 || isSaving}
        >
          {isSaving
            ? "Adding..."
            : `Add ${selectedSymbols.length} Symbol${
                selectedSymbols.length === 1 ? "" : "s"
              }`}
        </button>
      </div>
    </div>
  );
};

export default VolumeModal;
