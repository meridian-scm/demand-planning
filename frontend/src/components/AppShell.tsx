import { NavLink, Outlet } from 'react-router-dom';

import { navigationItems } from '../features/navigation/navigation';

function navClassName({ isActive }: { isActive: boolean }): string {
  return isActive ? 'nav-link nav-link--active' : 'nav-link';
}

export function AppShell() {
  const artifactDataVersion = import.meta.env.VITE_ARTIFACT_DATA_VERSION?.trim() || 'test-v1';

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <NavLink aria-label="Meridian home" className="brand" to="/">
          <span aria-hidden="true" className="brand-mark">
            M
          </span>
          <span>
            <strong>Meridian</strong>
            <small>Demand Planning</small>
          </span>
        </NavLink>

        <nav aria-label="Primary navigation" className="primary-navigation">
          {navigationItems.map((item) => (
            <NavLink
              className={navClassName}
              end={item.path === '/'}
              key={item.path}
              to={item.path}
            >
              <span aria-hidden="true" className="nav-monogram">
                {item.shortLabel}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-note">
          <span className="status-dot" />
          <div>
            <strong>Demo data active</strong>
            <span>Immutable {artifactDataVersion} artifacts</span>
          </div>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div>
            <span className="topbar-label">Planning workspace</span>
            <span className="topbar-context">Store + SKU + Month</span>
          </div>
          <span className="environment-badge">Development</span>
        </header>
        <main id="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
