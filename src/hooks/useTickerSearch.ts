import { useState, useEffect, useMemo } from "react";
import debounce from "lodash/debounce";
import { searchFinancialSymbols} from "../assets/APIs/TickerSearch";
import { type IndexSuggestion } from "../assets/APIs/StockFirestore";

export const useTickerSearch = () => {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState<IndexSuggestion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isFocused, setIsFocused] = useState(false);

  const fetchIndexData = async (searchQuery: string) => {
    if (searchQuery.length < 2) {
      setSuggestions(null);
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const data = await searchFinancialSymbols(searchQuery);
      setSuggestions(data);
    } catch (err: any) {
      setError(err.message || "Failed to fetch data.");
    } finally {
      setLoading(false);
    }
  };

  const debouncedFetch = useMemo(() => debounce(fetchIndexData, 400), []);

  useEffect(() => {
    debouncedFetch(query);
    return () => debouncedFetch.cancel();
  }, [query, debouncedFetch]);

  const clearSearch = () => {
    setQuery("");
    setSuggestions(null);
  };

  return {
    query,
    setQuery,
    suggestions,
    loading,
    error,
    setError,
    isFocused,
    setIsFocused,
    clearSearch,
  };
};