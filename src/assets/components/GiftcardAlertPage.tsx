import { useState, useEffect } from "react";
import {
  fetchAlerts,
  deleteAlert,
  toggleAlert,
  type GiftCardAlert,
} from "../APIs/GiftcardFirestore";
import CreateAlertModal from "./CreateGiftcardAlertModal";
import AlertCard from "./GiftcardAlertCard";

const EmptyState = ({ onAdd }: { onAdd: () => void }) => (
  <div className="d-flex flex-column align-items-center justify-content-center text-center" style={{ padding: "4rem 2rem", color: "#6c757d" }}>
    <div style={{ width: 56, height: 56, borderRadius: 12, background: "#f1f3f5", display: "flex", alignItems: "center", justifyContent: "center", marginBottom: "1rem" }}>
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="5" width="18" height="14" rx="2" stroke="#adb5bd" strokeWidth="1.5" />
        <path d="M7 9h10M7 13h6" stroke="#adb5bd" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="19" cy="19" r="4" fill="#f8f9fa" stroke="#adb5bd" strokeWidth="1.5" />
        <path d="M19 17v4M17 19h4" stroke="#adb5bd" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </div>
    <h5 style={{ fontWeight: 600, color: "#343a40", marginBottom: 6 }}>No gift card alerts yet</h5>
    <p style={{ fontSize: 14, maxWidth: 300, marginBottom: "1.5rem" }}>Create an alert to get notified when a gift card meets your discount criteria.</p>
    <button className="btn btn-primary btn-sm" onClick={onAdd}>+ New alert</button>
  </div>
);

const GiftCardAlertPage = () => {
  const [alerts, setAlerts] = useState<GiftCardAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  
  const loadAlerts = async () => {
    try {
      setLoading(true);
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
    loadAlerts();
  }, []);

  const handleToggle = async (alertId: string, newValue: boolean) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, isActive: newValue } : a))
    );
    try {
      await toggleAlert(alertId, newValue);
    } catch (err: any) {
      setAlerts((prev) =>
        prev.map((a) => (a.id === alertId ? { ...a, isActive: !newValue } : a))
      );
      setError(err.message || "Failed to update alert.");
    }
  };

  const handleDelete = async (alertId: string) => {
    const removed = alerts.find((a) => a.id === alertId);
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    try {
      await deleteAlert(alertId);
    } catch (err: any) {
      if (removed) setAlerts((prev) => [...prev, removed]);
      setError(err.message || "Failed to delete alert.");
    }
  };

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center p-3" style={{ borderBottom: "1px solid #e9ecef" }}>
        <h3 className="mb-0">Giftcard alerts</h3>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreateModal(true)}>+ New alert</button>
      </div>

      {error && (
        <div className="alert alert-danger mx-3 mt-3 mb-0 py-2" role="alert">
          <small>{error}</small>
        </div>
      )}

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