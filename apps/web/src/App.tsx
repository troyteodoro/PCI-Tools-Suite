import type { ReactNode } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from './components/AppShell';
import { useSession } from './lib/session';
import { BootstrapPage } from './routes/BootstrapPage';
import { LoginPage } from './routes/LoginPage';
import { AuditPage } from './routes/AuditPage';
import { DashboardPage } from './routes/DashboardPage';
import { PlaceholderPage } from './routes/PlaceholderPage';
import { TOOL_ROUTES } from './routes/routes';

function FullPageMessage({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        height: '100%',
        display: 'grid',
        placeItems: 'center',
        color: 'var(--app-text-muted)',
        fontSize: 12,
      }}
    >
      {children}
    </div>
  );
}

export function App() {
  const { session, deployment, isLoading } = useSession();

  if (isLoading) return <FullPageMessage>Loading…</FullPageMessage>;

  // First run: no account exists yet, so there is nothing to sign in to.
  if (deployment && !deployment.bootstrapped) {
    return (
      <Routes>
        <Route path="/setup" element={<BootstrapPage />} />
        <Route path="*" element={<Navigate to="/setup" replace />} />
      </Routes>
    );
  }

  if (!session) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/audit" element={<AuditPage />} />
        {TOOL_ROUTES.map((route) => (
          <Route
            key={route.path}
            path={route.path}
            element={
              <PlaceholderPage
                kicker={route.kicker}
                title={route.label}
                description={route.description}
                milestone={route.milestone}
                requirements={route.requirements}
              />
            }
          />
        ))}
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/setup" element={<Navigate to="/" replace />} />
        <Route path="*" element={<FullPageMessage>That page does not exist.</FullPageMessage>} />
      </Routes>
    </AppShell>
  );
}
