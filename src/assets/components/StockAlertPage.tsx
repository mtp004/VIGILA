import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import VolumeModal from "./VolumeModal";
import PositionSizingModal from "./PositionSizingModal";
import VolumeAlertCard from "./VolumeAlertCard";
import { type DashboardOutletContext } from "./Dashboard";

const StockAlertPage = () => {
  const { userSymbols, symbolsError, fetchSymbols, handleRemoveSymbol } =
    useOutletContext<DashboardOutletContext>();

  const [showVolumePopup, setShowVolumePopup] = useState(false);
  const [showPositionSizingPopup, setShowPositionSizingPopup] = useState(false);
  const [volumeSectionExpanded, setVolumeSectionExpanded] = useState(true);

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center p-3 border-bottom">
        <h3 className="mb-0">Notification list</h3>
        <div className="dropdown">
          <button className="btn btn-primary dropdown-toggle" type="button"
            data-bs-toggle="dropdown" data-bs-auto-close="outside">Menu</button>
          <ul className="dropdown-menu dropdown-menu-end">
            <li>
              <h6 className="dropdown-header" style={{ fontWeight: 700, color: "var(--bs-body-color, #212529)", textDecoration: "underline" }}>
                Alerts
              </h6>
            </li>
            <li>
              <a
                className="dropdown-item"
                href="#"
                style={{ paddingLeft: "2rem" }}
                onClick={(e) => { e.preventDefault(); setShowVolumePopup(true); }}
              >
                &bull; Volume
              </a>
            </li>
            <li><hr className="dropdown-divider" /></li>
            <li>
              <h6 className="dropdown-header" style={{ fontWeight: 700, color: "var(--bs-body-color, #212529)", textDecoration: "underline" }}>
                Analysis
              </h6>
            </li>
            <li>
              <a
                className="dropdown-item"
                href="#"
                style={{ paddingLeft: "2rem" }}
                onClick={(e) => { e.preventDefault(); setShowPositionSizingPopup(true); }}
              >
                &bull; Position sizing
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="flex-grow-1 overflow-hidden mt-4 mx-4 d-flex flex-column">
        <button
          type="button"
          className="btn d-flex align-items-center gap-2 px-0 mb-2"
          style={{ width: "fit-content", color: "inherit" }}
          onClick={() => setVolumeSectionExpanded((prev) => !prev)}
          aria-expanded={volumeSectionExpanded}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 16 16"
            fill="none"
            style={{
              transition: "transform 0.15s ease",
              transform: volumeSectionExpanded ? "rotate(90deg)" : "rotate(0deg)",
            }}
            aria-hidden="true"
          >
            <path
              d="M6 3l5 5-5 5"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          <h5 className="mb-0">Volume Alerts</h5>
        </button>

        {symbolsError && <div className="text-danger mb-2">{symbolsError}</div>}

        {volumeSectionExpanded && (
          <div className="flex-grow-1 overflow-auto">
            <VolumeAlertCard symbols={userSymbols} onRemove={handleRemoveSymbol} />
          </div>
        )}
      </div>

      {showVolumePopup && (
        <>
          <div className="modal-backdrop show"></div>
          <div className="modal d-block" tabIndex={-1}>
            <div className="modal-dialog modal-dialog-centered">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Volume</h5>
                  <button type="button" className="btn-close" onClick={() => setShowVolumePopup(false)}></button>
                </div>
                <div className="modal-body">
                  <VolumeModal
                    onAddSuccess={fetchSymbols}
                    existingSymbols={new Set(userSymbols.map(s => s.symbol))}
                  />
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {showPositionSizingPopup && (
        <>
          <div className="modal-backdrop show"></div>
          <div className="modal d-block" tabIndex={-1}>
            <div className="modal-dialog modal-dialog-centered">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Position Sizing</h5>
                  <button type="button" className="btn-close" onClick={() => setShowPositionSizingPopup(false)}></button>
                </div>
                <div className="modal-body">
                  <PositionSizingModal />
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default StockAlertPage;