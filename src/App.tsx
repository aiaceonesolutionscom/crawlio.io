import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import { Landing } from './pages/Landing';
import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { RequireAuth } from './routes/RequireAuth';
import { RequirePlan } from './routes/RequirePlan';
import { PlanRedirect } from './routes/PlanRedirect';

// Each tier is its own lazy chunk: a Free session never downloads Pro/Enterprise code.
const FreeLayout = lazy(() => import('./app/free/FreeLayout').then((m) => ({ default: m.FreeLayout })));
const FreeOverview = lazy(() => import('./app/free/pages/Overview').then((m) => ({ default: m.Overview })));
const FreeLeads = lazy(() => import('./app/free/pages/Leads').then((m) => ({ default: m.Leads })));
const FreeAutomation = lazy(() => import('./app/free/pages/Automation').then((m) => ({ default: m.Automation })));
const FreeAnalytics = lazy(() => import('./app/free/pages/Analytics').then((m) => ({ default: m.Analytics })));
const FreeTeam = lazy(() => import('./app/free/pages/Team').then((m) => ({ default: m.Team })));
const FreeSettings = lazy(() => import('./app/free/pages/Settings').then((m) => ({ default: m.Settings })));

const ProLayout = lazy(() => import('./app/pro/ProLayout').then((m) => ({ default: m.ProLayout })));
const ProOverview = lazy(() => import('./app/pro/pages/Overview').then((m) => ({ default: m.Overview })));
const ProLeads = lazy(() => import('./app/pro/pages/Leads').then((m) => ({ default: m.Leads })));
const ProAutomation = lazy(() => import('./app/pro/pages/Automation').then((m) => ({ default: m.Automation })));
const ProAnalytics = lazy(() => import('./app/pro/pages/Analytics').then((m) => ({ default: m.Analytics })));
const ProTeam = lazy(() => import('./app/pro/pages/Team').then((m) => ({ default: m.Team })));
const ProSettings = lazy(() => import('./app/pro/pages/Settings').then((m) => ({ default: m.Settings })));

const EnterpriseLayout = lazy(() => import('./app/enterprise/EnterpriseLayout').then((m) => ({ default: m.EnterpriseLayout })));
const EnterpriseOverview = lazy(() => import('./app/enterprise/pages/Overview').then((m) => ({ default: m.Overview })));
const EnterpriseLeads = lazy(() => import('./app/enterprise/pages/Leads').then((m) => ({ default: m.Leads })));
const EnterpriseAutomation = lazy(() => import('./app/enterprise/pages/Automation').then((m) => ({ default: m.Automation })));
const EnterpriseAnalytics = lazy(() => import('./app/enterprise/pages/Analytics').then((m) => ({ default: m.Analytics })));
const EnterpriseTeam = lazy(() => import('./app/enterprise/pages/Team').then((m) => ({ default: m.Team })));
const EnterpriseSettings = lazy(() => import('./app/enterprise/pages/Settings').then((m) => ({ default: m.Settings })));

function TierFallback() {
  return <div className="flex min-h-screen w-full items-center justify-center bg-ink-950 text-chalk-faint text-[13px]">Loading…</div>;
}

export function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Suspense fallback={<TierFallback />}>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />

            <Route path="/app" element={<RequireAuth><PlanRedirect /></RequireAuth>} />

            <Route
              path="/app/free"
              element={
              <RequireAuth>
                  <RequirePlan tier="free">
                    <FreeLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<FreeOverview />} />
              <Route path="leads" element={<FreeLeads />} />
              <Route path="automation" element={<FreeAutomation />} />
              <Route path="analytics" element={<FreeAnalytics />} />
              <Route path="team" element={<FreeTeam />} />
              <Route path="settings" element={<FreeSettings />} />
            </Route>

            <Route
              path="/app/pro"
              element={
              <RequireAuth>
                  <RequirePlan tier="pro">
                    <ProLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<ProOverview />} />
              <Route path="leads" element={<ProLeads />} />
              <Route path="automation" element={<ProAutomation />} />
              <Route path="analytics" element={<ProAnalytics />} />
              <Route path="team" element={<ProTeam />} />
              <Route path="settings" element={<ProSettings />} />
            </Route>

            <Route
              path="/app/enterprise"
              element={
              <RequireAuth>
                  <RequirePlan tier="enterprise">
                    <EnterpriseLayout />
                  </RequirePlan>
                </RequireAuth>
              }>

              <Route index element={<EnterpriseOverview />} />
              <Route path="leads" element={<EnterpriseLeads />} />
              <Route path="automation" element={<EnterpriseAutomation />} />
              <Route path="analytics" element={<EnterpriseAnalytics />} />
              <Route path="team" element={<EnterpriseTeam />} />
              <Route path="settings" element={<EnterpriseSettings />} />
            </Route>

            <Route path="/dashboard/*" element={<Navigate to="/app" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </AuthProvider>);

}
