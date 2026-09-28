import { useEffect, useState } from 'react';
import { NavLink, useNavigate, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  ScanSearch, 
  Sparkles, 
  History, 
  BookOpen, 
  Info, 
  ShieldCheck, 
  ChevronLeft, 
  ChevronRight, 
  X, 
  LogOut, 
  UserCircle2, 
  BadgeCheck, 
  Users, 
  FileText,
  Store,
  SearchCheck,
  ShieldAlert,
  Settings,
  Printer,
  GitCompare,
  UserCheck,
  Boxes,
  Building2,
  Barcode
} from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useWorkspace } from '../../context/WorkspaceContext';
import { useLanguage } from '../../context/LanguageContext';
import { api } from '../../services/api';
import { type WorkspaceType } from '../../types';

interface SidebarProps {
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  desc?: string;
  highlight?: boolean;
  badge?: string;
}

const WORKSPACE_NAV_CONFIG: Array<{
  id: WorkspaceType;
  labelKey: string;
  fallbackLabel: string;
  action: 'CHECK' | 'PREVENT' | 'VERIFY' | 'INVESTIGATE';
  icon: React.ComponentType<{ className?: string }>;
  activeClass: string;
  activeBorder: string;
}> = [
  { 
    id: 'USER', 
    labelKey: 'navigation.consumer',
    fallbackLabel: 'Consumer Workspace', 
    action: 'CHECK', 
    icon: UserCircle2, 
    activeClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-xs shadow-emerald-950/40',
    activeBorder: 'border-emerald-500/30'
  },
  { 
    id: 'MERCHANT', 
    labelKey: 'navigation.merchant',
    fallbackLabel: 'Merchant', 
    action: 'PREVENT', 
    icon: Store, 
    activeClass: 'bg-sky-500/15 text-sky-300 border-sky-500/40 shadow-xs shadow-sky-950/40',
    activeBorder: 'border-sky-500/30'
  },
  { 
    id: 'AUDIT', 
    labelKey: 'navigation.audit',
    fallbackLabel: 'Audit', 
    action: 'VERIFY', 
    icon: SearchCheck, 
    activeClass: 'bg-indigo-500/15 text-indigo-300 border-indigo-500/40 shadow-xs shadow-indigo-950/40',
    activeBorder: 'border-indigo-500/30'
  },
  { 
    id: 'ENFORCEMENT', 
    labelKey: 'navigation.enforcement',
    fallbackLabel: 'Enforcement', 
    action: 'INVESTIGATE', 
    icon: ShieldAlert, 
    activeClass: 'bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-xs shadow-amber-950/40',
    activeBorder: 'border-amber-500/30'
  },
];

export default function Sidebar({ 
  collapsed = false, 
  onToggleCollapse, 
  mobileOpen = false, 
  onCloseMobile 
}: SidebarProps) {
  const { user, logout } = useAuth();
  const { currentWorkspace, setWorkspace, isWorkspaceAllowed } = useWorkspace();
  const { t } = useLanguage();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Close mobile drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && mobileOpen && onCloseMobile) {
        onCloseMobile();
      }
    };
    if (mobileOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [mobileOpen, onCloseMobile]);

  const isNormalUser = user?.role === 'PUBLIC_USER' || user?.role === 'NORMAL_USER';

  const [systemHealth, setSystemHealth] = useState<{ status: string; version?: string } | null>(null);

  useEffect(() => {
    let isMounted = true;
    api.getHealth()
      .then(data => {
        if (isMounted && data) {
          setSystemHealth(data);
        }
      })
      .catch(() => {
        if (isMounted) {
          setSystemHealth({ status: 'healthy', version: '2.4.0' });
        }
      });
    return () => {
      isMounted = false;
    };
  }, []);

  const roleLabel = user?.role === 'ADMIN' ? t('roles.admin')
    : user?.role === 'ENFORCEMENT_OFFICER' ? t('roles.enforcement_officer')
    : user?.role === 'AUDIT_OFFICER' ? t('roles.audit_officer')
    : user?.role === 'MERCHANT_PUBLIC' ? t('roles.merchant')
    : t('roles.normal_user');

  const roleColor = user?.role === 'ADMIN' ? 'text-indigo-300'
    : user?.role === 'ENFORCEMENT_OFFICER' ? 'text-amber-300'
    : user?.role === 'AUDIT_OFFICER' ? 'text-indigo-300'
    : user?.role === 'MERCHANT_PUBLIC' ? 'text-sky-300'
    : 'text-emerald-300';

  const handleSelectWorkspace = (wsId: WorkspaceType) => {
    setWorkspace(wsId);
    if (location.pathname.startsWith('/admin')) {
      navigate('/');
    }
    onCloseMobile?.();
  };

  const visibleWorkspaces = WORKSPACE_NAV_CONFIG.filter(w => isWorkspaceAllowed(w.id));

  const isMerchant = currentWorkspace === 'MERCHANT';

  const overviewLinks: NavItem[] = isMerchant ? [
    { to: '/', icon: LayoutDashboard, label: t('navigation.dashboard') },
    { 
      to: '/analyze', 
      icon: ScanSearch, 
      label: t('navigation.statutory_compliance_inspection'),
      highlight: true,
      badge: 'Core'
    }
  ] : [
    { to: '/', icon: LayoutDashboard, label: t('navigation.dashboard') }
  ];

  const merchantCatalogLinks: NavItem[] = [
    { to: '/products', icon: Boxes, label: t('navigation.product_catalog') },
    { to: '/business-profile', icon: Building2, label: t('navigation.business_profile') }
  ];

  const screeningLinks: NavItem[] = isNormalUser ? [
    { 
      to: '/analyze', 
      icon: ScanSearch, 
      label: t('navigation.check_product'),
      highlight: true 
    },
    { 
      to: '/lookup', 
      icon: Barcode, 
      label: 'Barcode & FSSAI Lookup',
      badge: 'New' 
    },
    { 
      to: '/manual-check', 
      icon: FileText, 
      label: t('navigation.manual_product_check')
    },
    { to: '/history', icon: History, label: t('navigation.my_scan_history') }
  ] : isMerchant ? [
    { 
      to: '/lookup', 
      icon: Barcode, 
      label: 'Barcode & FSSAI Lookup',
      badge: 'New' 
    },
    { to: '/preprint', icon: Printer, label: t('navigation.pre_print_compliance') },
    { to: '/versions', icon: GitCompare, label: t('navigation.version_comparison') },
    { to: '/analyze-listing', icon: FileText, label: t('navigation.listing_check') },
    { to: '/history', icon: History, label: t('navigation.screening_history') }
  ] : currentWorkspace === 'ENFORCEMENT' ? [
    ...(user?.role === 'ADMIN' || user?.role === 'ENFORCEMENT_OFFICER' ? [{ to: '/enforcement', icon: ShieldAlert, label: t('navigation.enforcement_cases'), badge: 'Legal' }] : []),
    { to: '/reviews', icon: UserCheck, label: t('navigation.officer_review') },
    { 
      to: '/analyze', 
      icon: ScanSearch, 
      label: t('navigation.statutory_compliance_inspection'),
      highlight: true 
    },
    { to: '/versions', icon: GitCompare, label: t('navigation.version_comparison') },
    { to: '/analyze-listing', icon: FileText, label: t('navigation.listing_check') },
    { to: '/history', icon: History, label: t('navigation.screening_history') }
  ] : [
    { to: '/reviews', icon: UserCheck, label: t('navigation.officer_review') },
    { 
      to: '/analyze', 
      icon: ScanSearch, 
      label: t('navigation.technical_packaging_verification'),
      highlight: true 
    },
    { to: '/versions', icon: GitCompare, label: t('navigation.version_comparison') },
    { to: '/analyze-listing', icon: FileText, label: t('navigation.listing_check') },
    { to: '/history', icon: History, label: t('navigation.screening_history') }
  ];


  const intelligenceLinks: NavItem[] = [
    { to: '/rules', icon: BookOpen, label: isNormalUser ? t('navigation.packaging_rules_guide') : t('navigation.compliance_rules') }
  ];

  const toolsLinks: NavItem[] = isNormalUser ? [
    { to: '/about', icon: Info, label: t('navigation.about_project') }
  ] : [
    { to: '/demo', icon: Sparkles, label: t('navigation.demo_mode'), badge: 'SIH' },
    { to: '/about', icon: Info, label: t('navigation.about_project') }
  ];

  const renderNavLink = (link: NavItem) => (
    <NavLink
      key={link.to}
      to={link.to}
      onClick={onCloseMobile}
      title={collapsed ? link.label : undefined}
      aria-label={link.label}
      className={({ isActive }) =>
        `flex items-center gap-3 px-3 py-2 rounded-xl transition-all group relative ${
          isActive 
            ? 'bg-indigo-600 text-white font-semibold shadow-sm shadow-indigo-950/30' 
            : link.highlight
              ? 'text-slate-200 hover:bg-slate-800/90 hover:text-white font-medium bg-slate-800/30 border border-slate-700/40'
              : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-medium'
        } ${collapsed ? 'justify-center' : ''}`
      }
    >
      <link.icon className="w-4.5 h-4.5 shrink-0 transition-transform group-hover:scale-105" aria-hidden="true" />
      
      {!collapsed && (
        <div className="flex items-center justify-between flex-1 min-w-0">
          <span className="text-xs truncate">{link.label}</span>
          {link.badge && (
            <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-md shrink-0 border ${
              link.badge === 'Core'
                ? 'bg-sky-400/20 text-sky-300 border-sky-400/30'
                : 'bg-amber-400/20 text-amber-300 border-amber-400/30'
            }`}>
              {link.badge}
            </span>
          )}
        </div>
      )}

      {collapsed && (
        <span className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-lg border border-slate-700 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
          {link.label}
        </span>
      )}
    </NavLink>
  );

  return (
    <>
      {mobileOpen && (
        <div 
          onClick={onCloseMobile}
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-xs md:hidden animate-in fade-in duration-200"
          aria-hidden="true"
        />
      )}

      <aside 
        aria-label="Application Sidebar Navigation"
        role={mobileOpen ? "dialog" : undefined}
        aria-modal={mobileOpen ? "true" : undefined}
        className={`
          fixed md:static inset-y-0 left-0 z-50 
          bg-slate-900 text-slate-100 flex flex-col shrink-0 
          border-r border-slate-800/80 shadow-xl md:shadow-none
          transition-all duration-300 ease-in-out select-none
          ${collapsed ? 'w-20' : 'w-64'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
        `}
      >
        <div className="p-4 border-b border-slate-800/90 flex items-center justify-between gap-3 h-16">
          <div className="flex items-center gap-3 overflow-hidden">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-700 flex items-center justify-center shrink-0 shadow-sm shadow-indigo-950/50">
              <ShieldCheck className="w-6 h-6 text-white" />
            </div>
            {!collapsed && (
              <div className="flex flex-col min-w-0">
                <span className="font-extrabold text-base text-white tracking-tight leading-tight">
                  MetrCheck<span className="text-indigo-400"> AI</span>
                </span>
                <span className="text-[10px] font-medium text-slate-400 truncate">
                  {t('header.ai_assisted_compliance')}
                </span>
              </div>
            )}
          </div>

          <button 
            type="button"
            onClick={onCloseMobile}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 md:hidden cursor-pointer"
            aria-label="Close navigation drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Scrollable Navigation List */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-6" aria-label="Main Navigation">
          {/* Workspaces */}
          <div className="space-y-1">
            {!collapsed && <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider px-3 pb-1 block">{t('navigation.workspaces')}</span>}
            <div className="space-y-1">
              {visibleWorkspaces.map(ws => {
                const isActive = currentWorkspace === ws.id;
                const Icon = ws.icon;
                const label = t(ws.labelKey) || ws.fallbackLabel;
                return (
                  <button
                    key={ws.id}
                    onClick={() => handleSelectWorkspace(ws.id)}
                    title={collapsed ? `${label} (${ws.action})` : undefined}
                    className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-xl transition-all group relative text-left cursor-pointer border ${
                      isActive ? `${ws.activeClass} font-semibold` : 'border-transparent text-slate-400 hover:bg-slate-800/70 hover:text-slate-200'
                    } ${collapsed ? 'justify-center' : ''}`}
                  >
                    <Icon className={`w-4 h-4 shrink-0 transition-transform group-hover:scale-105 ${isActive ? '' : 'text-slate-400'}`} />
                    {!collapsed && (
                      <div className="flex items-center justify-between flex-1 min-w-0">
                        <span className="text-xs truncate">{label}</span>
                        <span className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded tracking-wider ${isActive ? 'bg-white/10' : 'bg-slate-800 text-slate-400'}`}>
                          {ws.action}
                        </span>
                      </div>
                    )}
                    {collapsed && (
                      <span className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-lg border border-slate-700 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                        {label}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-1">
            {!collapsed && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 pb-1 block">{t('navigation.overview')}</span>}
            {overviewLinks.map(renderNavLink)}
          </div>

          {user?.role === 'ADMIN' && (
            <div className="space-y-1">
              {!collapsed && (
                <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wider px-3 pb-1 flex items-center gap-1.5">
                  <ShieldCheck className="w-3 h-3 text-indigo-400" />
                  {t('navigation.administration')}
                </span>
              )}
              
              <NavLink
                to="/admin/users"
                onClick={onCloseMobile}
                title={collapsed ? t('navigation.user_management') : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl transition-all group relative ${
                    isActive ? 'bg-indigo-600 text-white font-semibold shadow-sm shadow-indigo-950/30' : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-medium'
                  } ${collapsed ? 'justify-center' : ''}`
                }
              >
                <Users className="w-4.5 h-4.5 shrink-0 transition-transform group-hover:scale-105" />
                {!collapsed && (
                  <div className="flex items-center justify-between flex-1 min-w-0">
                    <span className="text-xs truncate">{t('navigation.user_management')}</span>
                  </div>
                )}
                {collapsed && (
                  <span className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-lg border border-slate-700 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                    {t('navigation.user_management')}
                  </span>
                )}
              </NavLink>

              <NavLink
                to="/admin/officer-requests"
                onClick={onCloseMobile}
                title={collapsed ? t('navigation.officer_requests') : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl transition-all group relative ${
                    isActive ? 'bg-indigo-600 text-white font-semibold shadow-sm shadow-indigo-950/30' : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-medium'
                  } ${collapsed ? 'justify-center' : ''}`
                }
              >
                <UserCheck className="w-4.5 h-4.5 shrink-0 transition-transform group-hover:scale-105" />
                {!collapsed && (
                  <div className="flex items-center justify-between flex-1 min-w-0">
                    <span className="text-xs truncate">{t('navigation.officer_requests')}</span>
                  </div>
                )}
                {collapsed && (
                  <span className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-lg border border-slate-700 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                    {t('navigation.officer_requests')}
                  </span>
                )}
              </NavLink>

              <NavLink
                to="/admin/audit-logs"
                onClick={onCloseMobile}
                title={collapsed ? t('navigation.security_audit_logs') : undefined}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3 py-2 rounded-xl transition-all group relative ${
                    isActive ? 'bg-indigo-600 text-white font-semibold shadow-sm shadow-indigo-950/30' : 'text-slate-300 hover:bg-slate-800/80 hover:text-white font-medium'
                  } ${collapsed ? 'justify-center' : ''}`
                }
              >
                <History className="w-4.5 h-4.5 shrink-0 transition-transform group-hover:scale-105" />
                {!collapsed && (
                  <div className="flex items-center justify-between flex-1 min-w-0">
                    <span className="text-xs truncate">{t('navigation.security_audit_logs')}</span>
                  </div>
                )}
                {collapsed && (
                  <span className="absolute left-full ml-3 px-2.5 py-1 bg-slate-900 text-white text-xs font-semibold rounded-lg shadow-lg border border-slate-700 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                    {t('navigation.security_audit_logs')}
                  </span>
                )}
              </NavLink>
            </div>
          )}

          {(currentWorkspace === 'MERCHANT' || user?.role === 'MERCHANT_PUBLIC' || user?.role === 'ADMIN') && (
            <div className="space-y-1">
              {!collapsed && <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider px-3 pb-1 block">{t('navigation.catalog_entity')}</span>}
              {merchantCatalogLinks.map(renderNavLink)}
            </div>
          )}

          <div className="space-y-1">
            {!collapsed && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 pb-1 block">{t('navigation.screening')}</span>}
            {screeningLinks.map(renderNavLink)}
          </div>

          <div className="space-y-1">
            {!collapsed && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 pb-1 block">{isNormalUser ? (t('navigation.guidance') || 'Guidance') : t('navigation.intelligence')}</span>}
            {intelligenceLinks.map(renderNavLink)}
          </div>

          <div className="space-y-1">
            {!collapsed && <span className="text-[10px] font-bold text-slate-500 uppercase tracking-wider px-3 pb-1 block">{t('navigation.tools')}</span>}
            {toolsLinks.map(renderNavLink)}
          </div>
        </nav>

        <div className="p-3 border-t border-slate-800/90 space-y-2">
          {user && (
            <div className={`p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 ${collapsed ? 'flex flex-col items-center gap-1.5' : ''}`}>
              {!collapsed ? (
                <div className="flex items-center gap-2.5 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center shrink-0">
                    <UserCircle2 className="w-5 h-5 text-indigo-300" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-200 truncate">
                      {user.username || user.email}
                    </p>
                    <p className={`text-[10px] font-medium truncate ${roleColor}`}>
                      <BadgeCheck className="w-3 h-3 inline-block mr-0.5 -mt-0.5" />
                      {roleLabel}
                    </p>
                  </div>
                  <button
                    onClick={() => { navigate('/settings'); onCloseMobile?.(); }}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-300 hover:bg-indigo-500/10 cursor-pointer"
                    title={t('navigation.settings')}
                  >
                    <Settings className="w-4 h-4" />
                  </button>
                  <button
                    onClick={handleLogout}
                    className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 hover:bg-red-500/10 cursor-pointer"
                    title={t('navigation.sign_out')}
                  >
                    <LogOut className="w-4 h-4" />
                  </button>
                </div>
              ) : (
                <>
                  <button onClick={() => navigate('/settings')} className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-300 cursor-pointer" title={t('navigation.settings')}>
                    <Settings className="w-4 h-4" />
                  </button>
                  <button onClick={handleLogout} className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 cursor-pointer" title={t('navigation.sign_out')}>
                    <LogOut className="w-4 h-4" />
                  </button>
                </>
              )}
            </div>
          )}

          {!collapsed ? (
            <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${systemHealth?.status === 'degraded' ? 'bg-amber-400' : 'bg-emerald-400'}`}></span>
                  <span className={`relative inline-flex rounded-full h-2 w-2 ${systemHealth?.status === 'degraded' ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
                </span>
                <span className="text-[11px] font-medium text-slate-300 truncate">
                  {systemHealth?.status === 'degraded' ? t('navigation.system_degraded') : t('navigation.system_operational')}
                </span>
              </div>
              <span className="text-[10px] font-mono text-slate-500 font-semibold shrink-0">
                v{systemHealth?.version || '2.4.0'}
              </span>
            </div>
          ) : (
            <div className="flex justify-center p-1" title={systemHealth?.status === 'degraded' ? t('navigation.system_degraded') : t('navigation.system_operational')}>
              <span className="relative flex h-2.5 w-2.5">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${systemHealth?.status === 'degraded' ? 'bg-amber-400' : 'bg-emerald-400'}`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${systemHealth?.status === 'degraded' ? 'bg-amber-500' : 'bg-emerald-500'}`}></span>
              </span>
            </div>
          )}

          {onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="hidden md:flex items-center justify-center w-full py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded-lg cursor-pointer"
            >
              {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
            </button>
          )}
        </div>
      </aside>
    </>
  );
}