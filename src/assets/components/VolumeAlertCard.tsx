// src/components/VolumeAlertCard.tsx
import React from "react";
import { type VolumeAlert } from "../APIs/StockFirestore";

interface VolumeAlertCardProps {
  symbols: VolumeAlert[];
  onRemove: (symbol: VolumeAlert) => void;
}

interface SpikeInfo {
  dateLabel: string;
  badgeLabel?: string;
  background?: string;
}

function getSpikeInfo(lastAlertedDate: string | null): SpikeInfo {
  if (!lastAlertedDate) {
    return {
      dateLabel: "None",
    };
  }

  const [year, month, day] = lastAlertedDate.split("-").map(Number);
  const alertedDate = new Date(year, month - 1, day);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  alertedDate.setHours(0, 0, 0, 0);

  const daysAgo = Math.round((today.getTime() - alertedDate.getTime()) / 86400000);

  const dateLabel = alertedDate.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  if (daysAgo <= 1) {
    return {
      dateLabel,
      badgeLabel: "Today",
      background: "#991b1b",
    };
  }

  if (daysAgo <= 7) {
    return {
      dateLabel,
      badgeLabel: `${daysAgo} days ago`,
      background: "#cf8430",
    };
  }

  return {
    dateLabel,
    badgeLabel: `${daysAgo} days ago`,
    background: "#12b21a",
  };
}

const VolumeAlertCard: React.FC<VolumeAlertCardProps> = ({ symbols, onRemove }) => {
  if (symbols.length === 0) return <p>No saved symbols yet.</p>;

  return (
    <ul className="list-group">
      {symbols.map((s) => {
        const spike = getSpikeInfo(s.lastAlertedDate);

        return (
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

            <div className="d-flex align-items-center gap-2">
              <div className="text-muted small text-nowrap">
                Last alert trigger: {spike.dateLabel}
              </div>
              {spike.badgeLabel && (
                <span
                  className="badge rounded-pill text-nowrap"
                  style={{
                    background: spike.background,
                    color: "#fff",
                    fontWeight: 600,
                    fontSize: "12px",
                    padding: "5px 10px",
                  }}
                >
                  {spike.badgeLabel}
                </span>
              )}
            </div>

            <button
              className="btn btn-sm btn-outline-danger align-self-start align-self-md-center"
              onClick={() => onRemove(s)}
            >
              x
            </button>
          </li>
        );
      })}
    </ul>
  );
};

export default VolumeAlertCard;