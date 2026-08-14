import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';

import { ApiError, endpoints } from './api';
import type { DeploymentStatus, SessionResponse } from './api';

interface SessionContextValue {
  session: SessionResponse | null;
  deployment: DeploymentStatus | null;
  isLoading: boolean;
  logout: () => void;
}

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();

  const deploymentQuery = useQuery({
    queryKey: ['deployment'],
    queryFn: endpoints.deployment,
    staleTime: Infinity,
  });

  const sessionQuery = useQuery({
    queryKey: ['session'],
    queryFn: endpoints.session,
    // A 401 is the expected answer for a signed-out visitor, not a transient failure.
    retry: (failureCount, error) =>
      !(error instanceof ApiError && error.isUnauthenticated) && failureCount < 2,
    staleTime: 30_000,
  });

  const logoutMutation = useMutation({
    mutationFn: endpoints.logout,
    onSuccess: () => queryClient.clear(),
  });

  const value = useMemo<SessionContextValue>(
    () => ({
      session: sessionQuery.data ?? null,
      deployment: deploymentQuery.data ?? null,
      isLoading: sessionQuery.isLoading || deploymentQuery.isLoading,
      logout: () => logoutMutation.mutate(),
    }),
    [sessionQuery.data, sessionQuery.isLoading, deploymentQuery.data, deploymentQuery.isLoading, logoutMutation],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const context = useContext(SessionContext);
  if (!context) throw new Error('useSession must be used inside a SessionProvider');
  return context;
}

/** Throws if called outside an authenticated route. Saves null checks in every screen. */
export function useAuthenticatedSession(): SessionResponse {
  const { session } = useSession();
  if (!session) throw new Error('useAuthenticatedSession used outside an authenticated route');
  return session;
}
