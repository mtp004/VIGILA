import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { PATIENCE_OPTIONS, type GiftcardPatience } from "../APIs/GiftcardFirestore";
import { type DashboardOutletContext } from "./Dashboard";

const SettingsPage = () => {
  const { giftcardPatience, handleChangePatience } = useOutletContext<DashboardOutletContext>();
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const savingRef = useRef(false); // read by the beforeunload listener

  const index = PATIENCE_OPTIONS.findIndex((o) => o.value === giftcardPatience);

  useEffect(() => {
    // Have the browser confirm a reload or tab close until the write lands
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (savingRef.current) e.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  const select = async (patience: GiftcardPatience) => {
    if (savingRef.current || patience === giftcardPatience) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(null);
    try {
      await handleChangePatience(patience);
    } catch (err) {
      setSaveError((err instanceof Error && err.message) || "Failed to save setting.");
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  };

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="p-3" style={{ borderBottom: "1px solid #e9ecef" }}>
        <h3 className="mb-0">Settings</h3>
      </div>

      <div className="p-3">
        <div className="card" style={{ border: "1px solid #e9ecef", borderRadius: 12, maxWidth: 640 }}>
          <div className="card-body" style={{ padding: "1.25rem" }}>
            <div className="d-flex align-items-center justify-content-between mb-1">
              <div style={{ fontWeight: 600, fontSize: 15 }}>Alert Optimization</div>
              {saving && (
                <div className="d-flex align-items-center gap-2" style={{ fontSize: 12, color: "#6c757d" }}>
                  <span className="spinner-border spinner-border-sm" style={{ width: 14, height: 14 }} aria-hidden />
                  Saving...
                </div>
              )}
            </div>
            <div style={{ fontSize: 13, color: "#6c757d", marginBottom: 12 }}>
              Sets each alert's discount from price history. Wait longer, get alerted at bigger discounts.
            </div>

            <div
              role="radiogroup"
              aria-label="Alert Optimization"
              aria-busy={saving}
              className="position-relative d-flex"
              style={{
                background: "#f1f3f5",
                borderRadius: 10,
                padding: 3,
                maxWidth: 420,
                opacity: saving ? 0.6 : 1,
                transition: "opacity 0.15s",
              }}
            >
              <div
                aria-hidden
                style={{
                  position: "absolute",
                  top: 3,
                  bottom: 3,
                  left: 3,
                  width: `calc((100% - 6px) / ${PATIENCE_OPTIONS.length})`,
                  transform: `translateX(${index * 100}%)`,
                  transition: "transform 0.2s ease",
                  background: "#fff",
                  borderRadius: 8,
                  boxShadow: "0 1px 3px rgba(0, 0, 0, 0.12)",
                }}
              />
              {PATIENCE_OPTIONS.map((option, i) => {
                const active = i === index;
                return (
                  <button
                    key={option.value}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    disabled={saving}
                    onClick={() => select(option.value)}
                    className="position-relative flex-fill"
                    style={{
                      flexBasis: 0,
                      border: "none",
                      background: "transparent",
                      padding: "7px 4px",
                      fontSize: 13,
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                      color: active ? (option.value === "manual" ? "#212529" : "#0d6efd") : "#6c757d",
                      cursor: saving ? "not-allowed" : "pointer",
                    }}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>

            {saveError && <div className="text-danger mt-2" style={{ fontSize: 12 }}>{saveError}</div>}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
