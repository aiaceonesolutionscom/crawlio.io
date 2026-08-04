import React from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { DashboardLayout } from './components/dashboard/DashboardLayout';
import { Overview } from './pages/dashboard/Overview';
import { Leads } from './pages/dashboard/Leads';
import { Automation } from './pages/dashboard/Automation';
import { Analytics } from './pages/dashboard/Analytics';
import { Team } from './pages/dashboard/Team';
import { Settings } from './pages/dashboard/Settings';

function RequireAuth({ children }: {children: React.ReactNode;}) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          <Route
            path="/dashboard"
            element={
            <RequireAuth>
                <DashboardLayout />
              </RequireAuth>
            }>
            
            <Route index element={<Overview />} />
            <Route path="leads" element={<Leads />} />
            <Route path="automation" element={<Automation />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="team" element={<Team />} />
            <Route path="settings" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>);

}