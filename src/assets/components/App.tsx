import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Dashboard from './Dashboard'
import LoginPage from './LoginPage'
import ProtectedRoute from './ProtectedRoute' // Add this import

function App() {
  return (
    <Router>
      <Routes>
        // Login page //
        <Route path="/login" element={<LoginPage />} />

        // WARNING: ANYTHING IN THIS BLOCK HAS TO BE WRAPPED WITH PROTECTED ROUTE //
        <Route 
          path="/dashboard" 
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          } 
        />
        // WARNING: ANYTHING IN THIS BLOCK HAS TO BE WRAPPED WITH PROTECTED ROUTE //

        // Baseline route definition //
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Router>
  )
}

export default App