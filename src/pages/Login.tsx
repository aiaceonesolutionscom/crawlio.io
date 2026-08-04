import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, Loader2Icon } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Logo } from '../components/ui/Logo';
import { useAuth } from '../contexts/AuthContext';

export function Login() {
  const { login, isPending, error } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch {

      /* error surfaced from context */}
  };

  return (
    <div className="flex min-h-screen w-full flex-col bg-ink-950">
      <div className="mx-auto flex w-full max-w-[440px] flex-1 flex-col justify-center px-5 py-14">
        <Link to="/" className="mb-10 inline-flex items-center gap-2 text-[13px] text-chalk-faint hover:text-chalk">
          <ArrowLeftIcon className="h-3.5 w-3.5" />
          Back to site
        </Link>

        <Logo />
        <h1 className="mt-8 font-display text-[30px] font-semibold tracking-tight text-chalk">Welcome back</h1>
        <p className="mt-2 text-[15px] text-chalk-dim">Log in to your workspace to pick up the pipeline.</p>

        <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
          <div>
            <label htmlFor="login-email" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
              Work email
            </label>
            <input
              id="login-email"
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-3.5 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />
            
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between">
              <label htmlFor="login-password" className="block text-[13px] font-medium text-chalk-dim">
                Password
              </label>
              <a href="#reset" className="text-[12.5px] text-chalk-faint hover:text-signal">
                Forgot?
              </a>
            </div>
            <input
              id="login-password"
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 6 characters"
              className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-3.5 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />
            
          </div>

          {error &&
          <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
              {error}
            </p>
          }

          <Button type="submit" className="w-full" disabled={isPending}>
            {isPending ?
            <>
                <Loader2Icon className="h-4 w-4 animate-spin" />
                Signing in…
              </> :

            'Login'
            }
          </Button>
        </form>

        <p className="mt-6 text-center text-[14px] text-chalk-dim">
          No account yet?{' '}
          <Link to="/signup" className="font-medium text-signal hover:underline">
            Sign up free
          </Link>
        </p>
      </div>
    </div>);

}