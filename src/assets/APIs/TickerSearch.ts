import { type IndexSuggestion } from "./StockFirestore";

export const searchFinancialSymbols = async (searchQuery: string): Promise<IndexSuggestion[]> => {
  if (searchQuery.length < 2) {
    return [];
  }

  const API_KEY = import.meta.env.VITE_FINANCE_API_KEY;

  const response = await fetch(
    `https://financialmodelingprep.com/stable/search-symbol?query=${searchQuery}&apikey=${API_KEY}`
  );

  if (!response.ok) {
    throw new Error(
      "Network response was not ok. API key might be invalid or limit exceeded."
    );
  }

  return response.json();
};