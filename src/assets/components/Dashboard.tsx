import { auth } from '../../firebase'
import { signOut } from 'firebase/auth'
import { useState } from 'react'
import HomePage from './HomePage';
import 'bootstrap/dist/css/bootstrap.min.css';
import 'bootstrap/dist/js/bootstrap.bundle.min.js';

const Dashboard = () => {
  const user = auth.currentUser
  const [activeLink, setActiveLink] = useState('home')

  return (
    <div className="d-flex vh-100">
      {/* Static Sidebar */}
      <div 
        className="bg-dark text-white vh-100 p-3 d-flex flex-column"
        style={{ width: "200px" }}
      >
        {/* User Email (at the very top) - now wraps */}
        <div className=" text-break">
          {user?.email}
        </div>

        {/* Horizontal Rule */}
        <hr className="bg-light my-2" />

        {/* Navigation Links (in the middle) */}
        <ul className="nav flex-column mb-auto">
          <li className="nav-item">
            <a 
              className={`nav-link p-2 mb-2 rounded ${activeLink === 'home' ? 'bg-white text-dark' : 'text-white'}`}
              href="#"
              onClick={() => setActiveLink('home')}
            >
              Home
            </a>
          </li>
          <li className="nav-item">
            <a 
              className={`nav-link p-2 mb-2 rounded ${activeLink === 'settings' ? 'bg-white text-dark' : 'text-white'}`}
              href="#"
              onClick={() => setActiveLink('settings')}
            >
              Settings
            </a>
          </li>
        </ul>

        {/* Sign Out (at the bottom) */}
        <div className="mt-auto">
          <button
            className="btn btn-danger w-100 mt-2"
            onClick={() => signOut(auth)}
          >
            Sign Out
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-grow-1">
        {activeLink === "home" && <HomePage />}
        {activeLink === "settings" && <></>} {/* blank for now */}
      </div>
    </div>
  )
}

export default Dashboard