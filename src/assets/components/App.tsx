import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import Dashboard from './Dashboard'
import LoginPage from './LoginPage'
import ProtectedRoute from './ProtectedRoute'
import StockAlertPage from './StockAlertPage'
import GiftcardAlertPage from './GiftcardAlertPage'

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <Dashboard />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="stocks" replace /> },
      { path: 'stocks', element: <StockAlertPage /> },
      { path: 'giftcards', element: <GiftcardAlertPage /> },
      { path: 'settings', element: <></> },
    ],
  },
  {
    path: '/',
    element: <Navigate to="/dashboard" replace />,
  },
])

function App() {
  return <RouterProvider router={router} />
}

export default App