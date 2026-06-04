import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import VolumeModal from "./VolumeModal";
import SymbolListItem from "./SymbolListItem";
import { type DashboardOutletContext } from "./Dashboard";

const StockAlertPage = () => {
  const { userSymbols, symbolsError, fetchSymbols, handleRemoveSymbol } =
    useOutletContext<DashboardOutletContext>();

  const [showPopup, setShowPopup] = useState(false);

  return (
    <div className="vh-100 d-flex flex-column">
      <div className="d-flex justify-content-between align-items-center p-3 border-bottom">
        <h3 className="mb-0">Notification list</h3>
        <div className="dropdown">
          <button className="btn btn-primary dropdown-toggle" type="button"
            data-bs-toggle="dropdown" data-bs-auto-close="outside">+</button>
          <ul className="dropdown-menu dropdown-menu-end">
            <li>
              <a className="dropdown-item" href="#" onClick={(e) => { e.preventDefault(); setShowPopup(true); }}>
                Volume
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="flex-grow-1 overflow-hidden mt-4 mx-4 d-flex flex-column">
        <h5>Your Saved Volume Symbols</h5>
        {symbolsError && <div className="text-danger mb-2">{symbolsError}</div>}
        <div className="flex-grow-1 overflow-auto border rounded">
          <SymbolListItem symbols={userSymbols} onRemove={handleRemoveSymbol} />
        </div>
      </div>

      {showPopup && (
        <>
          <div className="modal-backdrop show"></div>
          <div className="modal d-block" tabIndex={-1}>
            <div className="modal-dialog modal-dialog-centered">
              <div className="modal-content">
                <div className="modal-header">
                  <h5 className="modal-title">Volume</h5>
                  <button type="button" className="btn-close" onClick={() => setShowPopup(false)}></button>
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
    </div>
  );
};

export default StockAlertPage;