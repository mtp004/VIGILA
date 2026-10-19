import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { PATIENCE_OPTIONS, type GiftcardPatience } from "../APIs/GiftcardFirestore";
import { type DashboardOutletContext } from "./Dashboard";

// Clicking cycles through options; save once the user stops clicking
const SAVE_DELAY_MS = 800;

const SettingsPage = () => {
  const { giftcardPatience, handleChangePatience } = useOutletContext<DashboardOutletContext>();
  const [selected, setSelected] = useState<GiftcardPatience>(giftcardPatience);
  const [saveError, setSaveError] = useState<string | null>(null);
  const pending = useRef<GiftcardPatience | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (pending.current === null) setSelected(giftcardPatience);
  }, [giftcardPatience]);

  const save = async () => {
    const value = pending.current;
    pending.current = null;
    if (value === null || value === giftcardPatience) return;
    try {
      await handleChangePatience(value);
    } catch (err: any) {
      setSelected(giftcardPatience);
      setSaveError(err.message || "Failed to save setting.");
    }
  };

  // Flush an unsaved choice if the user navigates away mid-cycle
  const saveRef = useRef(save);
  saveRef.current = save;
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
    saveRef.current();
  }, []);

  const cycle = () => {
    const index = PATIENCE_OPTIONS.findIndex((o) => o.value === selected);
    const next = PATIENCE_OPTIONS[(index + 1) % PATIENCE_OPTIONS.length].value;
    setSelected(next);
    setSaveError(null);
    pending.current = next;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(save, SAVE_DELAY_MS);
  };

  const selectedIndex = PATIENCE_OPTIONS.findIndex((o) => o.value === selected);
  const isAuto = selected !== "manual";

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="p-3" style={{ borderBottom: "1px solid #e9ecef" }}>
        <h3 className="mb-0">Settings</h3>
      </div>

      <div className="flex-grow-1 overflow-auto p-3">
        <div className="card" style={{ border: "1px solid #e9ecef", borderRadius: 12, maxWidth: 640 }}>
          <div className="card-body d-flex align-items-center gap-4" style={{ padding: "1.25rem" }}>
            <div className="flex-grow-1">
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Alert Optimization</div>
              <div style={{ fontSize: 13, color: "#6c757d", lineHeight: 1.5 }}>
                Sets each alert's discount from price history. Wait longer, get alerted at bigger discounts.
              </div>
            </div>

            <button
              type="button"
              onClick={cycle}
              aria-label={`Alert Optimization: ${PATIENCE_OPTIONS[selectedIndex].label}. Click to change.`}
              className="flex-shrink-0 d-flex flex-column align-items-center"
              style={{
                width: 112,
                padding: "8px 0 7px",
                borderRadius: 10,
                border: `1px solid ${isAuto ? "#0d6efd" : "#dee2e6"}`,
                background: isAuto ? "#f0f6ff" : "#fff",
                color: isAuto ? "#0d6efd" : "#495057",
                fontSize: 13,
                fontWeight: 600,
                transition: "all 0.15s",
              }}
            >
              {PATIENCE_OPTIONS[selectedIndex].label}
              <span className="d-flex gap-1 mt-1" aria-hidden>
                {PATIENCE_OPTIONS.slice(1).map((o, i) => (
                  <span
                    key={o.value}
                    style={{
                      width: 14,
                      height: 3,
                      borderRadius: 2,
                      background: i < selectedIndex ? "#0d6efd" : "#dee2e6",
                      transition: "background 0.15s",
                    }}
                  />
                ))}
              </span>
            </button>
          </div>

          {saveError && (
            <div className="alert alert-danger mx-3 mb-3 py-2" role="alert">
              <small>{saveError}</small>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
