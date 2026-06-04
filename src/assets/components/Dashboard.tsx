import { auth } from '../../firebase'
import { signOut } from 'firebase/auth'
import { useState, useEffect } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { fetchUserVolumeSymbols, removeVolumeSymbol, type IndexSuggestion } from '../APIs/StockFirestore'
import { fetchAlerts, deleteAlert, toggleAlert, type GiftCardAlert } from '../APIs/GiftcardFirestore'
import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

export interface DashboardOutletContext {
  // stocks
  userSymbols: IndexSuggestion[];
  symbolsError: string | null;
  fetchSymbols: () => Promise<void>;
  handleRemoveSymbol: (symbolObj: IndexSuggestion) => Promise<void>;
  
  // giftcards
  alerts: GiftCardAlert[];
  alertsLoading: boolean;
  alertsError: string | null;
  setAlertsError: (err: string | null) => void;
  loadAlerts: () => Promise<void>;
  handleToggle: (alertId: string, newValue: boolean) => Promise<void>;
  handleDelete: (alertId: string) => Promise<void>;
}

const Dashboard = () => {
  const user = auth.currentUser

  // STOCKS
  const [userSymbols, setUserSymbols] = useState<IndexSuggestion[]>([]);
  const [symbolsError, setSymbolsError] = useState<string | null>(null);

  const fetchSymbols = async () => {
    try {
      const symbols = await fetchUserVolumeSymbols();
      setUserSymbols(symbols);
    } catch (err: any) {
      setSymbolsError(err.message);
    }
  };

  const handleRemoveSymbol = async (symbolObj: IndexSuggestion) => {
    setUserSymbols((prev) => prev.filter((s) => s.symbol !== symbolObj.symbol));
    try {
      await removeVolumeSymbol(symbolObj);
    } catch (err: any) {
      setUserSymbols((prev) => [...prev, symbolObj]);
      setSymbolsError(err.message);
    }
  };
  // STOCKS


  // GIFTCARDS
  const [alerts, setAlerts] = useState<GiftCardAlert[]>([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState<string | null>(null);

  const loadAlerts = async () => {
    try {
      setAlertsLoading(true);
      setAlertsError(null);
      const data = await fetchAlerts();
      setAlerts(data);
    } catch (err: any) {
      setAlertsError(err.message || "Failed to load alerts.");
    } finally {
      setAlertsLoading(false);
    }
  };

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
      setAlertsError(err.message || "Failed to update alert.");
    }
  };

  const handleDelete = async (alertId: string) => {
    const removed = alerts.find((a) => a.id === alertId);
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
    try {
      await deleteAlert(alertId);
    } catch (err: any) {
      if (removed) setAlerts((prev) => [...prev, removed]);
      setAlertsError(err.message || "Failed to delete alert.");
    }
  };
  // GIFTCARDS


  useEffect(() => {
    fetchSymbols();
    loadAlerts();
  }, []);

  return (
    <div className="d-flex vh-100">
      <div className="bg-dark text-white vh-100 p-3 d-flex flex-column" style={{ width: "200px" }}>
        <div className="text-break">{user?.email}</div>
        <hr className="bg-light my-2" />
        <ul className="nav flex-column mb-auto">
          <li className="nav-item">
            <NavLink to="stocks"
              className={({ isActive }) =>
                `nav-link p-2 mb-2 rounded ${isActive ? 'bg-white text-dark' : 'text-white'}`
              }>Stocks</NavLink>
          </li>
          <li className="nav-item">
            <NavLink to="giftcards"
              className={({ isActive }) =>
                `nav-link p-2 mb-2 rounded ${isActive ? 'bg-white text-dark' : 'text-white'}`
              }>Gift card alerts</NavLink>
          </li>
          <li className="nav-item">
            <NavLink to="settings"
              className={({ isActive }) =>
                `nav-link p-2 mb-2 rounded ${isActive ? 'bg-white text-dark' : 'text-white'}`
              }>Settings</NavLink>
          </li>
        </ul>
        <div className="mt-auto">
          <button className="btn btn-danger w-100 mt-2" onClick={() => signOut(auth)}>Sign Out</button>
        </div>
      </div>

      <div className="flex-grow-1">
        <Outlet context={{
          userSymbols, symbolsError, fetchSymbols, handleRemoveSymbol,
          alerts, alertsLoading, alertsError, setAlertsError, loadAlerts, handleToggle, handleDelete
        } satisfies DashboardOutletContext} />
      </div>
    </div>
  )
}

export default Dashboard