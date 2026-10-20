import { useEffect, useRef, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { PATIENCE_OPTIONS, type GiftcardPatience } from "../APIs/GiftcardFirestore";
import { type DashboardOutletContext } from "./Dashboard";

const SAVE_DELAY_MS = 800; // clicking cycles options; save once the user stops

const SettingsPage = () => {
  const { giftcardPatience, handleChangePatience } = useOutletContext<DashboardOutletContext>();
  const [pending, setPending] = useState<GiftcardPatience | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const save = useRef<() => void>(() => {});

  const selected = pending ?? giftcardPatience;
  const index = PATIENCE_OPTIONS.findIndex((o) => o.value === selected);
  const isAuto = selected !== "manual";

  save.current = () => {
    clearTimeout(timer.current);
    setPending(null);
    if (pending && pending !== giftcardPatience) {
      handleChangePatience(pending).catch((err) => setSaveError(err.message || "Failed to save setting."));
    }
  };
  useEffect(() => () => save.current(), []); // save if the user leaves mid-cycle

  const cycle = () => {
    setPending(PATIENCE_OPTIONS[(index + 1) % PATIENCE_OPTIONS.length].value);
    setSaveError(null);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => save.current(), SAVE_DELAY_MS);
  };

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="p-3" style={{ borderBottom: "1px solid #e9ecef" }}>
        <h3 className="mb-0">Settings</h3>
      </div>

      <div className="p-3">
        <div className="card" style={{ border: "1px solid #e9ecef", borderRadius: 12, maxWidth: 640 }}>
          <div className="card-body d-flex align-items-center gap-4" style={{ padding: "1.25rem" }}>
            <div className="flex-grow-1">
              <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>Alert Optimization</div>
              <div style={{ fontSize: 13, color: "#6c757d" }}>
                Sets each alert's discount from price history. Wait longer, get alerted at bigger discounts.
              </div>
              {saveError && <div className="text-danger mt-2" style={{ fontSize: 12 }}>{saveError}</div>}
            </div>

            <button
              type="button"
              onClick={cycle}
              aria-label={`Alert Optimization: ${PATIENCE_OPTIONS[index].label}. Click to change.`}
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
              }}
            >
              {PATIENCE_OPTIONS[index].label}
              <span className="d-flex gap-1 mt-1" aria-hidden>
                {[1, 2, 3].map((step) => (
                  <span
                    key={step}
                    style={{ width: 14, height: 3, borderRadius: 2, background: step <= index ? "#0d6efd" : "#dee2e6" }}
                  />
                ))}
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SettingsPage;
