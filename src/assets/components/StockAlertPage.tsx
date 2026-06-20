import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import VolumeModal from "./VolumeModal";
import PositionSizingModal from "./PositionSizingModal";
import SymbolListItem from "./SymbolListItem";
import { type DashboardOutletContext } from "./Dashboard";

const StockAlertPage = () => {
  const { userSymbols, symbolsError, fetchSymbols, handleRemoveSymbol } =
    useOutletContext<DashboardOutletContext>();

  const [showVolumePopup, setShowVolumePopup] = useState(false);
  const [showPositionSizingPopup, setShowPositionSizingPopup] = useState(false);

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center p-3 border-bottom">
        <h3 className="mb-0">Notification list</h3>
        <div className="dropdown">
          <button className="btn btn-primary dropdown-toggle" type="button"
            data-bs-toggle="dropdown" data-bs-auto-close="outside">Menu</button>
          <ul className="dropdown-menu dropdown-menu-end">
            <li><h6 className="dropdown-header">Alerts</h6></li>
            <li>
              <a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); setShowVolumePopup(true); }}>
                Volume
              </a>
            </li>
            <li><hr className="dropdown-divider" /></li>
            <li><h6 className="dropdown-header">Analysis</h6></li>
            <li>
              <a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); setShowPositionSizingPopup(true); }}>
                Position sizing
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="flex-grow-1 overflow-hidden mt-4 mx-4 d-flex flex-column">
        <h5>Avtive Volume Alerts</h5>
        {symbolsError && <div className="text-danger mb-2">{symbolsError}</div>}
        <div className="flex-grow-1 overflow-auto border rounded">
          <SymbolListItem symbols={userSymbols} onRemove={handleRemoveSymbol} />
        </div>
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