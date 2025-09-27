import { useState, useEffect } from "react";
import VolumeModal from "./VolumeModal";
import SymbolListItem from "./SymbolListItem";
import { fetchUserVolumeSymbols, removeVolumeSymbol, type IndexSuggestion } from "../APIs/Firestore";

const HomePage = () => {
  const [showPopup, setShowPopup] = useState(false);
  const [userSymbols, setUserSymbols] = useState<IndexSuggestion[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchSymbols = async () => {
    try {
      const symbols = await fetchUserVolumeSymbols();
      setUserSymbols(symbols);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    fetchSymbols();
  }, []);

  const handleVolumeClick = () => {
    setShowPopup(true);
  };

  const handleRemoveSymbol = async (symbolObj: IndexSuggestion) => {
    setUserSymbols((prev) => prev.filter((s) => s.symbol !== symbolObj.symbol));
    try {
      await removeVolumeSymbol(symbolObj);
    } catch (err: any) {
      setUserSymbols((prev) => [...prev, symbolObj]);
      setError(err.message);
    }
  };

  return (
    <div className="vh-100 d-flex flex-column">
      {/* Top Bar */}
      <div className="d-flex justify-content-between align-items-center p-3 border-bottom">
        <h3 className="mb-0">Notification list</h3>
        <div className="dropdown">
            <button
                className="btn btn-primary dropdown-toggle"
                type="button"
                data-bs-toggle="dropdown"
                data-bs-auto-close="outside" 
            >
                +
            </button>
            <ul
                className={`dropdown-menu dropdown-menu-end`}
                
            >
                <li>
                <a
                    className="dropdown-item"
                    href="#"
                    onClick={(e) => {
                    e.preventDefault();
                    handleVolumeClick();
                    }}
                >
                    Volume
                </a>
                </li>
            </ul>
        </div>
      </div>

      {/* Content */}
      <div className="flex-grow-1 p-3">
        <h5>Your Saved Volume Symbols</h5>
        {error && <div className="text-danger mb-2">{error}</div>}
        {userSymbols.length === 0 ? (
          <p>No saved symbols yet.</p>
        ) : (
          <SymbolListItem symbols={userSymbols} onRemove={handleRemoveSymbol} />
        )}
      </div>

      {/* Modal */}
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
                  <VolumeModal onAddSuccess={fetchSymbols} />
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default HomePage;
