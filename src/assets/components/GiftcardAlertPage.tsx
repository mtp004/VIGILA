import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { type GiftCardAlert } from "../APIs/GiftcardFirestore";
import CreateAlertModal from "./CreateGiftcardAlertModal";
import GiftcardAlertCard from "./GiftcardAlertCard";
import { type DashboardOutletContext } from "./Dashboard";

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

const GiftcardAlertPage = () => {
  const {
    alerts,
    alertsLoading,
    alertsError,
    loadAlerts,
    handleToggle,
    handleDelete,
  } = useOutletContext<DashboardOutletContext>();

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAlert, setEditingAlert] = useState<GiftCardAlert | null>(null);

  const handleEdit = (alert: GiftCardAlert) => {
    setEditingAlert(alert);
    setShowCreateModal(true);
  };

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center p-3" style={{ borderBottom: "1px solid #e9ecef" }}>
        <h3 className="mb-0">Giftcard alerts</h3>
        <button className="btn btn-primary btn-sm" onClick={() => setShowCreateModal(true)}>+ New alert</button>
      </div>

      {alertsError && (
        <div className="alert alert-danger mx-3 mt-3 mb-0 py-2" role="alert">
          <small>{alertsError}</small>
        </div>
      )}

      <div className="flex-grow-1 overflow-auto p-3">
        {alertsLoading ? (
          <div className="d-flex justify-content-center align-items-center" style={{ height: "200px" }}>
            <div className="spinner-border spinner-border-sm text-secondary" role="status">
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState onAdd={() => setShowCreateModal(true)} />
        ) : (
          alerts.map((alert) => (
            <GiftcardAlertCard
              key={alert.id}
              alert={alert}
              onToggle={handleToggle}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ))
        )}
      </div>

      {showCreateModal && (
        <CreateAlertModal
          onAddSuccess={loadAlerts}
          editingAlert={editingAlert}
          onClose={() => { setShowCreateModal(false); setEditingAlert(null); }}
        />
      )}
    </div>
  );
};

export default GiftcardAlertPage;