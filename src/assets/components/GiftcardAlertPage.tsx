import { useState, useEffect } from "react";
import { Timestamp } from "firebase/firestore";
import {
  fetchAlerts,
  deleteAlert,
  toggleAlert,
  type GiftCardAlert,
} from "../APIs/GiftcardFirestore";
import CreateAlertModal from "./CreateGiftcardAlertModal";
// ─── Helpers ─────────────────────────────────────────────────────────────────

function getBrandInitials(brand: string): string {
  return brand
    .split(/[\s\-]+/)
    .filter(Boolean)
    .slice(0, 3)
    .map((w) => w[0].toUpperCase())
    .join("");
}

function formatTimestamp(ts: Timestamp | null): string {
  if (!ts) return "—";
  const date = ts.toDate();
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return date.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function formatCreatedAt(ts: Timestamp): string {
  return ts.toDate().toLocaleDateString([], {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ─── Platform Badge ───────────────────────────────────────────────────────────

const PLATFORM_LABELS: Record<string, string> = {
  gcx: "GCX",
  cardcash: "CardCash",
  carddepot: "CardDepot",
};

interface PlatformBadgeProps {
  platformId: string;
  enabled: boolean;
  satisfied: boolean;
}

const PlatformBadge = ({ platformId, enabled, satisfied }: PlatformBadgeProps) => {
  const label = PLATFORM_LABELS[platformId] ?? platformId;

  if (!enabled) {
    return (
      <span
        className="badge rounded-pill"
        style={{
          background: "#f1f3f5",
          color: "#adb5bd",
          fontWeight: 500,
          fontSize: "12px",
          padding: "5px 10px",
          border: "1px solid #e9ecef",
        }}
      >
        {label}
      </span>
    );
  }

  if (satisfied) {
    return (
      <span
        className="badge rounded-pill d-flex align-items-center gap-1"
        style={{
          background: "#d1fae5",
          color: "#065f46",
          fontWeight: 600,
          fontSize: "12px",
          padding: "5px 10px",
          border: "1px solid #a7f3d0",
        }}
      >
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5l2 2 4-4" stroke="#065f46" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        {label}
      </span>
    );
  }

  return (
    <span
      className="badge rounded-pill"
      style={{
        background: "#fff",
        color: "#495057",
        fontWeight: 500,
        fontSize: "12px",
        padding: "5px 10px",
        border: "1px solid #dee2e6",
      }}
    >
      {label}
    </span>
  );
};

// ─── Alert Card ───────────────────────────────────────────────────────────────

interface AlertCardProps {
  alert: GiftCardAlert;
  onToggle: (alertId: string, newValue: boolean) => void;
  onEdit: (alert: GiftCardAlert) => void;
  onDelete: (alertId: string) => void;
}

const AlertCard = ({ alert, onToggle, onEdit, onDelete }: AlertCardProps) => {
  const initials = getBrandInitials(alert.brand);
  const satisfiedSet = new Set(alert.satisfied_by);
  const satisfiedCount = alert.satisfied_by.length;
  const enabledPlatforms = Object.entries(alert.platforms).filter(([, v]) => v);

  return (
    <div
      className="card mb-3"
      style={{
        border: "1px solid #e9ecef",
        borderRadius: "12px",
        boxShadow: "none",
        opacity: alert.isActive ? 1 : 0.65,
        transition: "opacity 0.2s",
      }}
    >
      <div className="card-body" style={{ padding: "1rem 1.25rem" }}>
        {/* Header */}
        <div className="d-flex justify-content-between align-items-start mb-3">
          <div className="d-flex align-items-center gap-2">
            <div
              className="d-flex align-items-center justify-content-center flex-shrink-0"
              style={{
                width: 40,
                height: 40,
                borderRadius: 8,
                background: "#f1f3f5",
                fontSize: 13,
                fontWeight: 600,
                color: "#495057",
                letterSpacing: "0.02em",
              }}
            >
              {initials}
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 15, textTransform: "capitalize" }}>
                {alert.brand}
              </div>
              <div style={{ fontSize: 12, color: "#6c757d" }}>
                Created {formatCreatedAt(alert.createdAt)}
              </div>
            </div>
          </div>

          <div className="d-flex align-items-center gap-2">
            {/* Active toggle */}
            <div className="form-check form-switch mb-0">
              <input
                className="form-check-input"
                type="checkbox"
                role="switch"
                id={`toggle-${alert.id}`}
                checked={alert.isActive}
                onChange={() => onToggle(alert.id, !alert.isActive)}
                style={{ cursor: "pointer" }}
              />
            </div>
            {/* Edit */}
            <button
              className="btn btn-sm btn-light"
              style={{ padding: "4px 8px", border: "1px solid #dee2e6" }}
              onClick={() => onEdit(alert)}
              title="Edit alert"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M9.5 1.5l3 3L4 13H1v-3L9.5 1.5z"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
            {/* Delete */}
            <button
              className="btn btn-sm btn-light"
              style={{ padding: "4px 8px", border: "1px solid #dee2e6", color: "#dc3545" }}
              onClick={() => onDelete(alert.id)}
              title="Delete alert"
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M2 3.5h10M5 3.5V2.5h4v1M5.5 6v4M8.5 6v4M3 3.5l.75 8h6.5l.75-8"
                  stroke="currentColor"
                  strokeWidth="1.4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>
          </div>
        </div>

        {/* Meta pills */}
        <div className="row g-2 mb-3">
          <div className="col-4">
            <div
              style={{
                background: "#f8f9fa",
                borderRadius: 8,
                padding: "8px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "#6c757d", marginBottom: 2 }}>
                Card value
              </div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                ${alert.minCardValue} – ${alert.maxCardValue}
              </div>
            </div>
          </div>
          <div className="col-4">
            <div
              style={{
                background: "#f8f9fa",
                borderRadius: 8,
                padding: "8px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "#6c757d", marginBottom: 2 }}>
                Min discount
              </div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {alert.minDiscountPercent}% off
              </div>
            </div>
          </div>
          <div className="col-4">
            <div
              style={{
                background: "#f8f9fa",
                borderRadius: 8,
                padding: "8px 12px",
              }}
            >
              <div style={{ fontSize: 11, color: "#6c757d", marginBottom: 2 }}>
                Last checked
              </div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {formatTimestamp(alert.lastCheckedAt)}
              </div>
            </div>
          </div>
        </div>

        {/* Divider */}
        <hr style={{ margin: "0 0 12px", borderColor: "#f1f3f5" }} />

        {/* Platform badges + status */}
        <div className="d-flex align-items-center flex-wrap gap-2">
          {Object.entries(alert.platforms).map(([platformId, enabled]) => (
            <PlatformBadge
              key={platformId}
              platformId={platformId}
              enabled={enabled}
              satisfied={satisfiedSet.has(platformId)}
            />
          ))}

          <span
            className="ms-auto d-flex align-items-center gap-1"
            style={{ fontSize: 12, color: "#6c757d" }}
          >
            {!alert.isActive ? (
              <>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#adb5bd",
                    display: "inline-block",
                  }}
                />
                Paused
              </>
            ) : satisfiedCount > 0 ? (
              <>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#10b981",
                    display: "inline-block",
                  }}
                />
                Match found on{" "}
                {satisfiedCount === enabledPlatforms.length
                  ? "all platforms"
                  : `${satisfiedCount} platform${satisfiedCount > 1 ? "s" : ""}`}
              </>
            ) : (
              <>
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#dee2e6",
                    display: "inline-block",
                  }}
                />
                No match yet
              </>
            )}
          </span>
        </div>
      </div>
    </div>
  );
};

// ─── Empty State ──────────────────────────────────────────────────────────────

const EmptyState = ({ onAdd }: { onAdd: () => void }) => (
  <div
    className="d-flex flex-column align-items-center justify-content-center text-center"
    style={{ padding: "4rem 2rem", color: "#6c757d" }}
  >
    <div
      style={{
        width: 56,
        height: 56,
        borderRadius: 12,
        background: "#f1f3f5",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        marginBottom: "1rem",
      }}
    >
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="5" width="18" height="14" rx="2" stroke="#adb5bd" strokeWidth="1.5" />
        <path d="M7 9h10M7 13h6" stroke="#adb5bd" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="19" cy="19" r="4" fill="#f8f9fa" stroke="#adb5bd" strokeWidth="1.5" />
        <path d="M19 17v4M17 19h4" stroke="#adb5bd" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
    <h5 style={{ fontWeight: 600, color: "#343a40", marginBottom: 6 }}>
      No gift card alerts yet
    </h5>
    <p style={{ fontSize: 14, maxWidth: 300, marginBottom: "1.5rem" }}>
      Create an alert to get notified when a gift card meets your discount criteria.
    </p>
    <button className="btn btn-primary btn-sm" onClick={onAdd}>
      + New alert
    </button>
  </div>
);

// ─── Main Page ────────────────────────────────────────────────────────────────

const GiftCardAlertPage = () => {
  const [alerts, setAlerts] = useState<GiftCardAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  const loadAlerts = async () => {
    try {
      setError(null);
      const data = await fetchAlerts();
      setAlerts(data);
    } catch (err: any) {
      setError(err.message || "Failed to load alerts.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setLoading(false);
    return;
    loadAlerts();
  }, []);

  const handleToggle = async (alertId: string, newValue: boolean) => {
    // Optimistic update
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, isActive: newValue } : a))
    );
    try {
      await toggleAlert(alertId, newValue);
    } catch (err: any) {
      // Revert on failure
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, isActive: !newValue } : a))
      );
      setError(err.message || "Failed to update alert.");
    }
  };

  const handleDelete = async (alertId: string) => {
    const removed = alerts.find((a) => a.id === alertId);
    // Optimistic removal
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    try {
      await deleteAlert(alertId);
    } catch (err: any) {
      // Revert on failure
      if (removed) setAlerts((prev) => [...prev, removed]);
      setError(err.message || "Failed to delete alert.");
    }
  };

  return (
    <div className="vh-100 d-flex flex-column">
      {/* Page header */}
      <div
        className="d-flex justify-content-between align-items-center p-3"
        style={{ borderBottom: "1px solid #e9ecef" }}
      >
        <h3 className="mb-0" style={{ fontSize: 18, fontWeight: 600 }}>
          Gift card alerts
        </h3>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreateModal(true)}>
          + New alert
        </button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="alert alert-danger mx-3 mt-3 mb-0 py-2" role="alert">
          <small>{error}</small>
        </div>
      )}

      {/* Content */}
      <div className="flex-grow-1 overflow-auto p-3">
        {loading ? (
          <div className="d-flex justify-content-center align-items-center" style={{ height: "200px" }}>
            <div className="spinner-border spinner-border-sm text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState onAdd={() => setShowCreateModal(true)} />
        ) : (
          alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onToggle={handleToggle}
              onEdit={() => {/* EditAlertModal coming next */}}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>
      {showCreateModal && (
        <CreateAlertModal
          onAddSuccess={loadAlerts}
          onClose={() => setShowCreateModal(false)}
        />
      )}
    </div>
  );
};

export default GiftCardAlertPage;