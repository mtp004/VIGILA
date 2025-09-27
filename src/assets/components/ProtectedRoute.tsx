import React, { useState, useEffect } from 'react';
import type { ReactNode } from 'react'; // Use type-only import
import { onAuthStateChanged} from 'firebase/auth';
import type {User} from 'firebase/auth';
import { Navigate } from 'react-router-dom';
import { auth } from '../../firebase'

interface ProtectedRouteProps {
  children: ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user: User | null) => {
      setUser(user);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  if (loading) {
    return (
      <div className="d-flex justify-content-center align-items-center min-vh-100">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }
  
  return user ? <>{children}</> : <Navigate to="/login" replace />;
};

export default ProtectedRoute;