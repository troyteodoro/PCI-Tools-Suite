import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';

import { useAuthenticatedSession, useSession } from '../lib/session';
import { TOOL_ROUTES } from '../routes/routes';
import { useTheme } from '../theme/ThemeProvider';
import { CoachRail } from './CoachRail';
import { Icon, ThemeIcon } from './icons';
import styles from './AppShell.module.css';

/** The three-pane layout from the mockup: nav, content, PCI Coach rail. */
export function AppShell({ children }: { children: ReactNode }) {
  const session = useAuthenticatedSession();
  const { logout } = useSession();
  const { theme, toggleTheme } = useTheme();

  const tools = TOOL_ROUTES.filter((route) => route.section === 'tools');
  const assessment = TOOL_ROUTES.filter((route) => route.section === 'assessment');

  const navClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.navItem} ${styles.navItemActive}` : styles.navItem;

  return (
    <div className={styles.shell}>
      <nav className={styles.sidebar} aria-label="Primary">
        <div className={styles.brand}>
          <div className={styles.brandMark} aria-hidden="true" />
          <div>
            <div className={styles.brandName}>Demarc</div>
            <div className={styles.brandStandard}>PCI DSS v4.0.1</div>
          </div>
        </div>

        <div className={styles.navGroup}>
          <NavLink to="/" end className={navClass}>
            <Icon name="dashboard" />
            <span className={styles.navLabel}>Dashboard</span>
          </NavLink>

          <div className={styles.navSectionLabel}>Tools</div>
          {tools.map((route) => (
            <NavLink key={route.path} to={route.path} className={navClass}>
              <Icon name={route.icon} />
              <span className={styles.navLabel}>{route.label}</span>
              <span className={styles.navBadge}>{route.milestone}</span>
            </NavLink>
          ))}

          <div className={styles.navSectionLabel}>Assessment</div>
          {assessment.map((route) => (
            <NavLink key={route.path} to={route.path} className={navClass}>
              <Icon name={route.icon} />
              <span className={styles.navLabel}>{route.label}</span>
              <span className={styles.navBadge}>{route.milestone}</span>
            </NavLink>
          ))}
          <NavLink to="/audit" className={navClass}>
            <Icon name="audit" />
            <span className={styles.navLabel}>Audit log</span>
          </NavLink>
        </div>

        <div className={styles.sidebarFooter}>
          <div>
            <div className={styles.orgName}>{session.organization.name}</div>
            <div className={styles.orgMeta}>
              {formatMerchantLevel(session.organization.merchant_level)} · SAQ{' '}
              {session.organization.saq_type}
            </div>
          </div>
          <div className={styles.orgMeta} title={session.user.email}>
            {session.user.full_name} · {session.role}
          </div>
          <div className={styles.footerActions}>
            <button
              type="button"
              className={styles.iconButton}
              onClick={toggleTheme}
              aria-label={`Switch to ${theme === 'modernist' ? 'Nocturne' : 'Modernist'} theme`}
            >
              <ThemeIcon dark={theme === 'nocturne'} />
              {theme === 'modernist' ? 'Nocturne' : 'Modernist'}
            </button>
            <button type="button" className={styles.iconButton} onClick={logout}>
              Sign out
            </button>
          </div>
        </div>
      </nav>

      <main className={styles.main}>{children}</main>

      <CoachRail />
    </div>
  );
}

function formatMerchantLevel(level: string): string {
  const map: Record<string, string> = {
    level_1: 'Level 1 merchant',
    level_2: 'Level 2 merchant',
    level_3: 'Level 3 merchant',
    level_4: 'Level 4 merchant',
    service_provider: 'Service provider',
    undeclared: 'Level undeclared',
  };
  return map[level] ?? level;
}
