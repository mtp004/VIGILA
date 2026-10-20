import { lazy, Suspense } from 'react'
import { createBrowserRouter, RouterProvider, Navigate } from 'react-router-dom'
import LoginPage from './LoginPage'
import ProtectedRoute from './ProtectedRoute'

// Loaded after sign-in, so the login page doesn't download Firestore or the dashboard
const Dashboard = lazy(() => import('./Dashboard'))
const StockAlertPage = lazy(() => import('./StockAlertPage'))
const GiftcardAlertPage = lazy(() => import('./GiftcardAlertPage'))
const SettingsPage = lazy(() => import('./SettingsPage'))

const loading = (
  <div className="d-flex justify-content-center align-items-center min-vh-100">
    <p className="text-muted">Loading...</p>
  </div>
)

const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/dashboard',
    element: (
      <ProtectedRoute>
        <Suspense fallback={loading}>
          <Dashboard />
        </Suspense>
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="stocks" replace /> },
      { path: 'stocks', element: <StockAlertPage /> },
      { path: 'giftcards', element: <GiftcardAlertPage /> },
      { path: 'settings', element: <SettingsPage /> },
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