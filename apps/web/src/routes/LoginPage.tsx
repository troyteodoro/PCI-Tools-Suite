import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';

import { ApiError, endpoints } from '../lib/api';
import { useSession } from '../lib/session';
import { AuthLayout } from './AuthLayout';

export function LoginPage() {
  const queryClient = useQueryClient();
  const { deployment } = useSession();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const login = useMutation({
    mutationFn: () => endpoints.login({ email, password }),
    onSuccess: (session) => {
      queryClient.setQueryData(['session'], session);
      void queryClient.invalidateQueries();
    },
  });

  const errorMessage =
    login.error instanceof ApiError
      ? login.error.message
      : login.error
        ? 'Could not reach the server.'
        : null;

  return (
    <AuthLayout
      title="Sign in"
      subtitle="Evidence, scope and readiness for your PCI DSS assessment."
      error={errorMessage}
      footer={
        deployment?.deployment_mode === 'single_tenant'
          ? 'Single-tenant deployment. Accounts are created by your administrator.'
          : null
      }
    >
      <form
        onSubmit={(event) => {
          event.preventDefault();
          login.mutate();
        }}
      >
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            className="input"
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        <button type="submit" className="btn btn-primary btn-block" disabled={login.isPending}>
          {login.isPending ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </AuthLayout>
  );
}
