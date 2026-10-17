import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Layers,
  Database,
  BarChart3,
  Mail,
  LogOut,
  Menu,
  X,
  Shield,
  Building,
  Sparkles,
  MessageSquare,
} from 'lucide-react';
import { useAuth } from '../../core/auth/AuthContext';

export const AppShell: React.FC = () => {
  const { user, logout, isRecruiterOrAdmin } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navGroups = [
    {
      label: 'Overview',
      items: [
        {
          to: '/dashboard',
          label: 'Dashboard',
          icon: LayoutDashboard,
          visible: true,
        },
      ],
    },
    {
      label: 'Hiring Operations',
      items: [
        {
          to: '/jobs',
          label: 'Jobs & Capabilities',
          icon: Briefcase,
          visible: isRecruiterOrAdmin,
        },
        {
          to: '/candidates',
          label: 'Candidates Pool',
          icon: Users,
          visible: isRecruiterOrAdmin,
        },
        {
          to: '/screening',
          label: 'Screening Queue',
          icon: Layers,
          visible: isRecruiterOrAdmin,
        },
      ],
    },
    {
      label: 'Interviews & Intelligence',
      items: [
        {
          to: '/interview-datasets',
          label: 'Question Datasets',
          icon: Database,
          visible: isRecruiterOrAdmin,
        },
      ],
    },
    {
      label: 'Insights & Audit',
      items: [
        {
          to: '/analytics',
          label: 'Evidence Analytics',
          icon: BarChart3,
          visible: isRecruiterOrAdmin,
        },
        {
          to: '/hiring-intelligence',
          label: 'Hiring Intelligence',
          icon: Sparkles,
          visible: isRecruiterOrAdmin,
        },
        {
          to: '/hiring-chat',
          label: 'HireIQ Chat (RAG)',
          icon: MessageSquare,
          visible: isRecruiterOrAdmin,
        },
      ],
    },
    {
      label: 'System & Ingestion',
      items: [
        {
          to: '/settings/email',
          label: 'Email Ingestion',
          icon: Mail,
          visible: isRecruiterOrAdmin,
        },
      ],
    },
  ];

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: 'var(--bg-app)' }}>
      {/* Desktop Sidebar */}
      <aside
        style={{
          width: '260px',
          backgroundColor: '#FFFFFF',
          borderRight: '1px solid var(--border-base)',
          display: 'flex',
          flexDirection: 'column',
          position: 'sticky',
          top: 0,
          height: '100vh',
          zIndex: 40,
        }}
        className="hidden md:flex"
      >
        {/* Brand Header */}
        <div
          style={{
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border-base)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
          }}
        >
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--primary-600)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '1.1rem',
              boxShadow: 'var(--shadow-sm)',
            }}
          >
            G
          </div>
          <div>
            <div style={{ fontSize: '1.1rem', fontWeight: 700, color: 'var(--text-main)', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
              Gap<span style={{ color: 'var(--primary-600)' }}>2</span>Hire
            </div>
            <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 500, lineHeight: 1 }}>
              Evidence-Based Hiring
            </div>
          </div>
        </div>

        {/* Navigation Items */}
        <div style={{ padding: '1rem 0.75rem', flex: 1, overflowY: 'auto' }}>
          {navGroups.map((group) => {
            const visibleItems = group.items.filter((item) => item.visible);
            if (visibleItems.length === 0) return null;

            return (
              <div key={group.label} style={{ marginBottom: '1.25rem' }}>
                <div
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    color: 'var(--text-tertiary)',
                    letterSpacing: '0.06em',
                    padding: '0 0.75rem 0.5rem',
                  }}
                >
                  {group.label}
                </div>
                {visibleItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.to}
                      to={item.to}
                      style={({ isActive }) => ({
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.65rem',
                        padding: '0.55rem 0.75rem',
                        borderRadius: 'var(--radius-md)',
                        fontSize: '0.875rem',
                        fontWeight: isActive ? 600 : 500,
                        color: isActive ? 'var(--primary-700)' : 'var(--text-secondary)',
                        backgroundColor: isActive ? 'var(--primary-50)' : 'transparent',
                        marginBottom: '0.15rem',
                        transition: 'all var(--transition-fast)',
                      })}
                    >
                      <Icon size={18} />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            );
          })}
        </div>

        {/* User Card & Logout */}
        {user && (
          <div
            style={{
              padding: '1rem',
              borderTop: '1px solid var(--border-base)',
              backgroundColor: 'var(--bg-subtle)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', overflow: 'hidden' }}>
                <div
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: '50%',
                    backgroundColor: 'var(--border-strong)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 600,
                    fontSize: '0.8rem',
                    color: 'var(--text-main)',
                  }}
                >
                  {user.full_name?.charAt(0) || 'U'}
                </div>
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ fontSize: '0.8125rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user.full_name}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user.email}
                  </div>
                </div>
              </div>
              <button
                onClick={handleLogout}
                className="btn btn-ghost btn-sm"
                title="Log Out"
                style={{ padding: '0.35rem', color: 'var(--text-muted)' }}
              >
                <LogOut size={16} />
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  padding: '0.15rem 0.45rem',
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: '#FFFFFF',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--border-base)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.2rem',
                }}
              >
                <Shield size={10} />
                {user.role}
              </span>
            </div>
          </div>
        )}
      </aside>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Topbar */}
        <header
          style={{
            height: '60px',
            backgroundColor: '#FFFFFF',
            borderBottom: '1px solid var(--border-base)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '0 1.5rem',
            position: 'sticky',
            top: 0,
            zIndex: 30,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="btn btn-ghost md:hidden"
              style={{ padding: '0.4rem' }}
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              <Building size={16} />
              <span>Workspace:</span>
              <strong style={{ color: 'var(--text-main)' }}>Enterprise Talent Pool</strong>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {user && (
              <span
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--text-secondary)',
                  backgroundColor: 'var(--bg-subtle)',
                  padding: '0.25rem 0.6rem',
                  borderRadius: 'var(--radius-full)',
                  border: '1px solid var(--border-base)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.35rem',
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: '50%', backgroundColor: '#10B981' }} />
                {user.role}
              </span>
            )}
          </div>
        </header>

        {/* Page Content Viewport */}
        <main style={{ flex: 1, padding: '1.5rem', overflowY: 'auto' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
