import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, ArrowLeft } from 'lucide-react';
import authBgImg from '../assets/auth-bg.png';
import { useAuth } from '../context/AuthContext';

// Official Google 'G' Icon
function GoogleIcon({ className = "w-5 h-5" }) {
  return (
    <svg className={className} viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
      />
    </svg>
  );
}

export default function Login() {
  const [gmailId, setGmailId] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const validateGmail = (email) => {
    const trimmed = email.trim();
    if (!trimmed) return 'Gmail ID is required.';
    // Basic email format validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(trimmed)) {
      return 'Please enter a valid email address.';
    }
    return null;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    const emailErr = validateGmail(gmailId);
    if (emailErr) {
      setError(emailErr);
      return;
    }

    if (!password) {
      setError('Password is required.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters.');
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await login(gmailId, password);
      if (result.success) {
        navigate('/dashboard');
      } else {
        setError('Invalid Gmail ID or password.');
      }
    } catch (err) {
      setError('Invalid Gmail ID or password.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
    setIsSubmitting(true);
    try {
      const result = await loginWithGoogle();
      if (result.success) {
        navigate('/dashboard');
      } else {
        setError(result.message || 'Google authentication failed.');
      }
    } catch (err) {
      setError('Google authentication failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      className="min-h-screen w-full flex flex-col justify-center items-center relative p-4 selection:bg-blue-600 selection:text-white font-sans overflow-x-hidden"
      style={{ backgroundColor: '#FFFFFF' }}
    >
      {/* High-quality full-page background image */}
      <img
        src={authBgImg}
        alt=""
        aria-hidden="true"
        style={{
          position: 'fixed',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          objectPosition: 'center',
          zIndex: 0,
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      />
      {/* Top Right: Functional Back to Home navigation */}
      <div className="fixed top-6 right-6 sm:top-8 sm:right-10 z-30">
        <Link
          to="/"
          id="back-to-home-link"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-[#0066FF] hover:text-[#0052CC] transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Home</span>
        </Link>
      </div>

      {/* Central Blank Area Form Container */}
      <div className="w-full max-w-[430px] px-6 sm:px-8 py-6 my-auto" style={{ position: 'relative', zIndex: 1 }}>
        
        {/* Form Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-[#0F172A] mb-1.5">
            Welcome Back
          </h1>
          <p className="text-xs sm:text-sm font-medium text-slate-500">
            Sign in to your Cloud ops LLM account
          </p>
        </div>

        {/* Clean Inline Validation Error Message */}
        {error && (
          <div className="mb-4 p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-700 text-xs font-semibold text-center animate-fadeIn">
            {error}
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          
          {/* Gmail ID Field */}
          <div className="space-y-1.5 text-left">
            <label className="text-xs font-bold text-slate-700 block">
              Gmail ID
            </label>
            <input
              id="login-gmail-input"
              type="text"
              required
              value={gmailId}
              onChange={(e) => {
                setGmailId(e.target.value);
                if (error) setError('');
              }}
              placeholder="Enter your Gmail ID"
              className="w-full px-4 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-900 text-sm placeholder-slate-400 focus:outline-none focus:border-[#0066FF] focus:ring-1 focus:ring-[#0066FF] transition-all shadow-2xs"
            />
          </div>

          {/* Password Field */}
          <div className="space-y-1.5 text-left">
            <label className="text-xs font-bold text-slate-700 block">
              Password
            </label>
            <div className="relative">
              <input
                id="login-password-input"
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (error) setError('');
                }}
                placeholder="Enter your password"
                className="w-full pl-4 pr-11 py-2.5 rounded-xl bg-white border border-slate-200 text-slate-900 text-sm placeholder-slate-400 focus:outline-none focus:border-[#0066FF] focus:ring-1 focus:ring-[#0066FF] transition-all shadow-2xs"
              />
              <button
                type="button"
                id="toggle-password-visibility"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 p-1 cursor-pointer transition-colors"
                aria-label={showPassword ? 'Hide password' : 'Show password'}
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            
            {/* Forgot Password Link */}
            <div className="flex justify-end pt-0.5">
              <Link
                to="/forgot-password"
                id="forgot-password-link"
                className="text-xs font-medium text-[#0066FF] hover:underline"
              >
                Forgot password?
              </Link>
            </div>
          </div>

          {/* Primary Login Button */}
          <button
            id="login-submit-button"
            type="submit"
            disabled={isSubmitting}
            className="w-full py-2.5 rounded-xl bg-[#0066FF] hover:bg-[#0055D4] text-white font-semibold text-sm shadow-sm hover:shadow-md transition-all duration-200 flex items-center justify-center cursor-pointer disabled:opacity-70 mt-2"
          >
            {isSubmitting ? (
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            ) : (
              'Login'
            )}
          </button>
        </form>

        {/* Divider: ──────────── or ──────────── */}
        <div className="flex items-center my-4 select-none">
          <div className="flex-1 border-t border-slate-200" />
          <span className="px-3 text-xs font-medium text-slate-400 uppercase tracking-wider">
            or
          </span>
          <div className="flex-1 border-t border-slate-200" />
        </div>

        {/* Google OAuth Login Button */}
        <button
          type="button"
          id="google-login-button"
          onClick={handleGoogleLogin}
          disabled={isSubmitting}
          className="w-full py-2.5 rounded-xl bg-white hover:bg-slate-50 border border-slate-200 text-slate-700 font-semibold text-sm shadow-2xs hover:shadow-xs transition-all duration-200 flex items-center justify-center gap-2.5 cursor-pointer disabled:opacity-70"
        >
          <GoogleIcon className="w-4 h-4" />
          <span>Continue with Google</span>
        </button>

        {/* Bottom Link: Don't have an account? Sign Up */}
        <div className="text-center mt-6">
          <p className="text-xs text-slate-500">
            Don't have an account?{' '}
            <Link
              to="/signup"
              id="signup-link"
              className="font-bold text-[#0066FF] hover:underline cursor-pointer"
            >
              Sign Up
            </Link>
          </p>
        </div>

      </div>
    </div>
  );
}
