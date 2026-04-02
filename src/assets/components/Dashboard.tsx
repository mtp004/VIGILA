import { auth } from '../../firebase'
import { signOut } from 'firebase/auth'
import { useState, useEffect } from 'react'
import HomePage from './HomePage';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';
import { fetchUserVolumeSymbols, removeVolumeSymbol, type IndexSuggestion } from '../APIs/Firestore';

const Dashboard = () => {
  const user = auth.currentUser
  const [activeLink, setActiveLink] = useState('home')
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

  useEffect(() => {
    fetchSymbols();
  }, []);

  const handleRemoveSymbol = async (symbolObj: IndexSuggestion) => {
    setUserSymbols((prev) => prev.filter((s) => s.symbol !== symbolObj.symbol));
    try {
      await removeVolumeSymbol(symbolObj);
    } catch (err: any) {
      setUserSymbols((prev) => [...prev, symbolObj]);
      setSymbolsError(err.message);
    }
  };

  return (
    <div className="d-flex vh-100">
      <div className="bg-dark text-white vh-100 p-3 d-flex flex-column" style={{ width: "200px" }}>
        <div className="text-break">{user?.email}</div>
        <hr className="bg-light my-2" />
        <ul className="nav flex-column mb-auto">
          <li className="nav-item">
            <a className={`nav-link p-2 mb-2 rounded ${activeLink === 'home' ? 'bg-white text-dark' : 'text-white'}`}
              href="#" onClick={() => setActiveLink('home')}>Home</a>
          </li>
          <li className="nav-item">
            <a className={`nav-link p-2 mb-2 rounded ${activeLink === 'settings' ? 'bg-white text-dark' : 'text-white'}`}
              href="#" onClick={() => setActiveLink('settings')}>Settings</a>
          </li>
        </ul>
        <div className="mt-auto">
          <button className="btn btn-danger w-100 mt-2" onClick={() => signOut(auth)}>Sign Out</button>
        </div>
      </div>

      <div className="flex-grow-1">
        {activeLink === "home" && (
          <HomePage
            userSymbols={userSymbols}
            onRemoveSymbol={handleRemoveSymbol}
            onAddSuccess={fetchSymbols}
            error={symbolsError}
          />
        )}
        {activeLink === "settings" && <></>}
      </div>
    </div>
  )
}

export default Dashboard