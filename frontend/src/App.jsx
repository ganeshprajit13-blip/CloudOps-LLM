import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { ProfileProvider } from './context/ProfileContext';

import Welcome from './pages/Welcome';
import Layout from './components/Layout';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';

import Dashboard from './pages/Dashboard';
import Incidents from './pages/Incidents';
import IncidentDetails from './pages/IncidentDetails';
import Troubleshooter from './pages/Troubleshooter';
import SupportAgent from './pages/SupportAgent';
import Logs from './pages/Logs';
import Resources from './pages/Resources';
import History from './pages/History';
import KnowledgeBase from './pages/KnowledgeBase';
import Billing from './pages/Billing';
import Settings from './pages/Settings';
import Profile from './pages/Profile';

// Protected Route Guard for Dashboard Routes
function ProtectedRoute({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-screen bg-[#F0F7FF] flex flex-col items-center justify-center space-y-3">
        <div className="w-8 h-8 border-3 border-[#0284C7] border-t-transparent rounded-full animate-spin" />
        <span className="text-xs font-semibold text-[#0369A1]">Verifying CloudOps Authentication...</span>
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

export default function App() {
  return (
    <LanguageProvider>
      <ThemeProvider>
        <AuthProvider>
          <ProfileProvider>
          <BrowserRouter>
            <Routes>
              {/* 1. Default Route: Welcome / Landing Page */}
              <Route path="/" element={<Welcome />} />

              {/* 2. Authentication Pages */}
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/signup" element={<Register />} />
              <Route path="/forgot-password" element={<ForgotPassword />} />

              {/* 3. Protected Dashboard Routes */}
              <Route
                element={
                  <ProtectedRoute>
                    <Layout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/incidents" element={<Incidents />} />
                <Route path="/incident/:id" element={<IncidentDetails />} />
                <Route path="/troubleshoot" element={<Troubleshooter />} />
                <Route path="/support-agent" element={<SupportAgent />} />
                <Route path="/logs" element={<Logs />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/history" element={<History />} />
                <Route path="/knowledge" element={<KnowledgeBase />} />
                <Route path="/billing" element={<Billing />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/profile" element={<Profile />} />
              </Route>

              {/* Fallback Catch-all -> Redirect to Welcome Page */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </BrowserRouter>
          </ProfileProvider>
        </AuthProvider>
      </ThemeProvider>
    </LanguageProvider>
  );
}
