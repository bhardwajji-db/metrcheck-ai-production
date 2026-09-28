import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { lazy, Suspense } from 'react';
import type { ReactNode } from 'react';
import { ThemeProvider } from './context/ThemeContext';
import { LanguageProvider } from './context/LanguageContext';
import { WorkspaceProvider } from './context/WorkspaceContext';
import { RoleProvider } from './context/RoleContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/layout/Layout';
// Eagerly loaded: auth flows, lightweight public pages, and Dashboard
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import ActivateAccount from './pages/ActivateAccount';
import AdminLogin from './pages/AdminLogin';
import ComplianceRules from './pages/ComplianceRules';
import About from './pages/About';
import DemoCases from './pages/DemoCases';
import ErrorBoundary from './components/ui/ErrorBoundary';

// Lazily loaded: heavy workspace pages (chart-heavy, enforcement, officer, products)
const Analyze = lazy(() => import('./pages/Analyze'));
const ManualProductCheck = lazy(() => import('./pages/ManualProductCheck'));
const AnalyzeListing = lazy(() => import('./pages/AnalyzeListing'));
const Results = lazy(() => import('./pages/Results'));
const History = lazy(() => import('./pages/History'));
const PrePrintCompliance = lazy(() => import('./pages/PrePrintCompliance'));
const VersionComparison = lazy(() => import('./pages/VersionComparison'));
const OfficerDashboard = lazy(() => import('./pages/OfficerDashboard'));
const ReviewWorkspace = lazy(() => import('./pages/ReviewWorkspace'));
const EnforcementDashboard = lazy(() => import('./pages/EnforcementDashboard'));
const EnforcementCaseWorkspace = lazy(() => import('./pages/EnforcementCaseWorkspace'));
const Products = lazy(() => import('./pages/Products'));
const ProductNew = lazy(() => import('./pages/ProductNew'));
const ProductDetail = lazy(() => import('./pages/ProductDetail'));
const ProductEdit = lazy(() => import('./pages/ProductEdit'));
const BusinessProfile = lazy(() => import('./pages/BusinessProfile'));
const AccountSettings = lazy(() => import('./pages/AccountSettings'));
const AdminUsers = lazy(() => import('./pages/AdminUsers'));
const BarcodeFssaiLookup = lazy(() => import('./pages/BarcodeFssaiLookup'));


function RequireAuth({ children }: { children: ReactNode }) {
  const { token, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-950">
        <div className="flex items-center gap-3 text-slate-400">
          <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Restoring session…</span>
        </div>
      </div>
    );
  }

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

function AdminOnly({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user || user.role !== 'ADMIN') {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}

/**
 * MerchantOrAdmin — frontend UX guard for product catalog routes.
 * Redirects non-merchant, non-admin roles to the home dashboard.
 * Backend authorization is the security boundary; this is a UX improvement
 * that prevents PUBLIC_USER and officer roles from entering product pages
 * and receiving a raw 403 response.
 */
function MerchantOrAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  const allowedRoles = ['MERCHANT_PUBLIC', 'ADMIN'];
  if (!allowedRoles.includes(user.role)) {
    return <Navigate to="/" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}


function App() {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <AuthProvider>
          <WorkspaceProvider>
            <RoleProvider>
            <BrowserRouter>
              <Suspense fallback={
                <div className="min-h-screen flex items-center justify-center bg-slate-950">
                  <div className="flex items-center gap-3 text-slate-400">
                    <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    <span className="text-sm">Loading…</span>
                  </div>
                </div>
              }>
                <Routes>
                  {/* Public pages */}
                  <Route path="/login" element={<Login />} />
                  <Route path="/admin/login" element={<AdminLogin />} />
                  <Route path="/forgot-password" element={<ForgotPassword />} />
                  <Route path="/reset-password" element={<ResetPassword />} />
                  <Route path="/activate" element={<ActivateAccount />} />
                  <Route path="/activate-account" element={<ActivateAccount />} />
                  <Route element={<Layout />}>
                    <Route path="/demo" element={<DemoCases />} />
                    <Route path="/rules" element={<ComplianceRules />} />
                    <Route path="/about" element={<About />} />

                    {/* Protected pages (role-based access) */}
                    <Route path="/" element={<RequireAuth><Dashboard /></RequireAuth>} />
                    <Route path="/products" element={<RequireAuth><MerchantOrAdmin><Products /></MerchantOrAdmin></RequireAuth>} />
                    <Route path="/products/new" element={<RequireAuth><MerchantOrAdmin><ProductNew /></MerchantOrAdmin></RequireAuth>} />
                    <Route path="/products/:productId" element={<RequireAuth><MerchantOrAdmin><ProductDetail /></MerchantOrAdmin></RequireAuth>} />
                    <Route path="/products/:productId/edit" element={<RequireAuth><MerchantOrAdmin><ProductEdit /></MerchantOrAdmin></RequireAuth>} />
                    <Route path="/business-profile" element={<RequireAuth><BusinessProfile /></RequireAuth>} />
                    <Route path="/analyze" element={<RequireAuth><Analyze /></RequireAuth>} />
                    <Route path="/lookup" element={<RequireAuth><BarcodeFssaiLookup /></RequireAuth>} />
                    <Route path="/manual-check" element={<RequireAuth><ManualProductCheck /></RequireAuth>} />
                    <Route path="/analyze-listing" element={<RequireAuth><AnalyzeListing /></RequireAuth>} />
                    <Route path="/preprint" element={<RequireAuth><PrePrintCompliance /></RequireAuth>} />
                    <Route path="/versions" element={<RequireAuth><VersionComparison /></RequireAuth>} />
                    <Route path="/reviews" element={<RequireAuth><OfficerDashboard /></RequireAuth>} />
                    <Route path="/reviews/:reviewId" element={<RequireAuth><ReviewWorkspace /></RequireAuth>} />
                    <Route path="/enforcement" element={<RequireAuth><EnforcementDashboard /></RequireAuth>} />
                    <Route path="/enforcement/cases/:caseId" element={<RequireAuth><EnforcementCaseWorkspace /></RequireAuth>} />
                    <Route path="/results/:id" element={<RequireAuth><ErrorBoundary><Results /></ErrorBoundary></RequireAuth>} />
                    <Route path="/history" element={<RequireAuth><History /></RequireAuth>} />
                    <Route path="/settings" element={<RequireAuth><AccountSettings /></RequireAuth>} />
                    <Route path="/admin/users" element={<RequireAuth><AdminOnly><AdminUsers defaultTab="users" /></AdminOnly></RequireAuth>} />
                    <Route path="/admin/officer-requests" element={<RequireAuth><AdminOnly><AdminUsers defaultTab="requests" /></AdminOnly></RequireAuth>} />
                    <Route path="/admin/audit-logs" element={<RequireAuth><AdminOnly><AdminUsers defaultTab="audit" /></AdminOnly></RequireAuth>} />
                  </Route>

                  <Route path="*" element={<Navigate to="/" />} />
                </Routes>
              </Suspense>
            </BrowserRouter>
          </RoleProvider>
        </WorkspaceProvider>
      </AuthProvider>
      </LanguageProvider>
    </ThemeProvider>
  );
}

export default App;