// src/components/VolumeSymbolList.tsx
import React from "react";
import { type IndexSuggestion } from "../APIs/Firestore";

interface SymbolListItemProps {
  symbols: IndexSuggestion[];
  onRemove: (symbol: IndexSuggestion) => void;
}

const SymbolListItem: React.FC<SymbolListItemProps> = ({ symbols, onRemove }) => {
  if (symbols.length === 0) return <p>No saved symbols yet.</p>;

  return (
    <ul className="list-group">
      {symbols.map((s) => (
        <li
          key={s.symbol}
          className="list-group-item d-flex justify-content-between align-items-start flex-column flex-md-row gap-2"
        >
          <div className="flex-grow-1">
            <div>
              <strong>{s.name}</strong> ({s.symbol})
            </div>
            <div className="text-muted small">
              Exchange: {s.exchange} ({s.exchangeFullName}) | Currency: {s.currency}
            </div>
          </div>
          <button
            className="btn btn-sm btn-outline-danger align-self-start align-self-md-center"
            onClick={() => onRemove(s)}
          >
            x
          </button>
        </li>
      ))}
    </ul>
  );
};

export default SymbolListItem;
