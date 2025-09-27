import { useState, useEffect } from 'react';
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, onAuthStateChanged } from 'firebase/auth';
import { sendEmailVerification } from "firebase/auth";
import { auth } from '../../firebase';
import { useNavigate } from 'react-router-dom';

const LoginPage = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [checkingAuth, setCheckingAuth] = useState(true);

  const navigate = useNavigate();

  // redirect if logged in
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (user) => {
      if (user?.emailVerified) {
        navigate('/dashboard');
      }
      setCheckingAuth(false);
    });
    return () => unsubscribe();
  }, [navigate]);


  const handleSubmit = async () => {
    setLoading(true);
    setError('');
    
    let userCredential;
    if(email==import.meta.env.VITE_AUTHORIZED_EMAIL){
      try {
        if (isLogin) {
          userCredential = await signInWithEmailAndPassword(auth, email, password);
          if (!userCredential.user.emailVerified) {
            await auth.signOut(); 
            setError("Please check your Spam, Junk, Inbox folders to verify your email before signing in.");
          }
        }else {
          userCredential = await createUserWithEmailAndPassword(auth, email, password);
          auth.signOut(); 
          await sendEmailVerification(userCredential.user);
          setIsLogin(true);
          setError("Please check your Spam, Junk, Inbox folders to verify your email before logging in");
        }
      } catch (err: any) {
        setLoading(false);
        setError(err.message);
      }
    } else{
      setError("Service currently not available for the public");
    }
    setLoading(false);
  };

  if (checkingAuth) {
    return (
      <div className="d-flex justify-content-center align-items-center">
        <p className="text-muted">Checking authentication...</p>
      </div>
    );
  }

  return (
    <div className="d-flex justify-content-center align-items-center min-vh-100 w-100">
      <div className="shadow p-5 rounded bg-white" style={{ width: '100%', maxWidth: '450px' }}>
        
        {/* Header */}
        <div className="text-center mb-4">
          <h2 className="h3 fw-bold text-primary mb-2">VIGILA</h2>
          <p className="text-muted mb-0">
            {isLogin ? 'Sign in to your account' : 'Create your account'}
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="alert alert-danger py-2" role="alert">
            <small>{error}</small>
          </div>
        )}

        {/* Form */}
        <form onSubmit={(e) => { e.preventDefault(); handleSubmit(); }}>
          {/* Email */}
          <div className="mb-3">
            <label htmlFor="email" className="form-label">Email</label>
            <input
              type="email"
              className="form-control"
              id="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="Enter your email"
            />
          </div>

          {/* Password */}
          <div className="mb-4">
            <label htmlFor="password" className="form-label">Password</label>
            <input
              type="password"
              className="form-control"
              id="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              autoComplete={isLogin ? "current-password" : "new-password"}
              placeholder="Enter your password"
            />
          </div>

          {/* Submit Button */}
          <div className="d-grid mb-3">
            <button
              type="submit"
              disabled={loading}
              className="btn btn-primary"
            >
              {loading && (
                <span className="spinner-border spinner-border-sm me-2" role="status" />
              )}
              {loading ? 'Please wait...' : (isLogin ? 'Sign In' : 'Create Account')}
            </button>
          </div>
        </form>

        {/* Divider */}
        <hr />

        {/* Toggle */}
        <div className="text-center">
          <span className="text-muted me-2">
            {isLogin ? "Don't have an account?" : 'Already have an account?'}
          </span>
          <button
            type="button"
            className="btn btn-link p-0 text-decoration-none"
            onClick={() => {
              setIsLogin(!isLogin);
              setError('');
            }}
          >
            {isLogin ? 'Sign up' : 'Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
