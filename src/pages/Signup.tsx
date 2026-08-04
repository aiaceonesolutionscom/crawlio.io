import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ArrowLeftIcon, CheckIcon, Loader2Icon } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Logo } from '../components/ui/Logo';
import { useAuth } from '../contexts/AuthContext';
import { PLANS } from '../data/plans';
import { cn } from '../utils/cn';
import type { PlanId } from '../types';

interface SignupState {
  email?: string;
  plan?: PlanId;
}

export function Signup() {
  const { signup, isPending, error } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const state = (location.state ?? {}) as SignupState;

  const [name, setName] = useState('');
  const [email, setEmail] = useState(state.email ?? '');
  const [password, setPassword] = useState('');
  const [plan, setPlan] = useState<PlanId>(state.plan ?? 'free');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await signup({ name, email, password, plan });
      navigate('/dashboard');
    } catch {

      /* error surfaced from context */}
  };

  return (
    <div className="min-h-screen w-full bg-ink-950">
      <div className="mx-auto grid w-full max-w-[1080px] gap-12 px-5 py-14 lg:grid-cols-[1fr_1fr] lg:gap-16 lg:py-20">
        <div>
          <Link to="/" className="mb-10 inline-flex items-center gap-2 text-[13px] text-chalk-faint hover:text-chalk">
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            Back to site
          </Link>

          <Logo />
          <h1 className="mt-8 font-display text-[32px] font-semibold leading-tight tracking-tight text-chalk">
            Create your workspace
          </h1>
          <p className="mt-2 text-[15px] text-chalk-dim">
            We provision an isolated workspace on your chosen plan — quotas, roles and defaults included.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 space-y-4" noValidate>
            <div>
              <label htmlFor="signup-name" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                Full name
              </label>
              <input
                id="signup-name"
                required
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Alex Moreau"
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-3.5 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />
              
            </div>

            <div>
              <label htmlFor="signup-email" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                Work email
              </label>
              <input
                id="signup-email"
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-3.5 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />
              
            </div>

            <div>
              <label htmlFor="signup-password" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                Password
              </label>
              <input
                id="signup-password"
                type="password"
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 6 characters"
                className="h-11 w-full rounded-lg border border-ink-700 bg-ink-900 px-3.5 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none" />
              
            </div>

            <fieldset>
              <legend className="mb-2 text-[13px] font-medium text-chalk-dim">Choose your plan</legend>
              <div className="space-y-2">
                {PLANS.map((option) => {
                  const selected = plan === option.id;
                  return (
                    <label
                      key={option.id}
                      className={cn(
                        'flex cursor-pointer items-start gap-3 rounded-xl border p-3.5 transition-colors',
                        selected ? 'border-signal bg-ink-850' : 'border-ink-700 bg-ink-900 hover:border-ink-600'
                      )}>
                      
                      <input
                        type="radio"
                        name="plan"
                        value={option.id}
                        checked={selected}
                        onChange={() => setPlan(option.id)}
                        className="sr-only" />
                      
                      <span
                        aria-hidden="true"
                        className={cn(
                          'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border',
                          selected ? 'border-signal bg-signal' : 'border-ink-600'
                        )}>
                        
                        {selected && <CheckIcon className="h-3 w-3 text-signal-deep" strokeWidth={3} />}
                      </span>
                      <span className="flex-1">
                        <span className="flex items-center justify-between gap-3">
                          <span className="text-[14.5px] font-medium text-chalk">{option.name}</span>
                          <span className="font-mono text-[12px] text-chalk-dim">{option.price}</span>
                        </span>
                        <span className="mt-0.5 block text-[12.5px] text-chalk-faint">
                          {option.leadQuota} · {option.seats}
                        </span>
                      </span>
                    </label>);

                })}
              </div>
            </fieldset>

            {error &&
            <p
              role="alert"
              className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
              
                {error}
              </p>
            }

            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ?
              <>
                  <Loader2Icon className="h-4 w-4 animate-spin" />
                  Provisioning workspace…
                </> :

              'Create workspace'
              }
            </Button>

            <p className="text-center text-[14px] text-chalk-dim">
              Already have an account?{' '}
              <Link to="/login" className="font-medium text-signal hover:underline">
                Login
              </Link>
            </p>
          </form>
        </div>

        <aside className="hidden rounded-2xl border border-ink-800 bg-ink-900 p-7 lg:block">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">What happens next</h2>
          <ol className="mt-6 space-y-6">
            {[
            { t: 'Workspace created', d: 'Isolated tenant with your own data boundary and owner role.' },
            { t: 'Plan quotas applied', d: 'Lead and seat limits are enforced server-side from day one.' },
            { t: 'Defaults seeded', d: 'A sample campaign, scoring model and starter dashboard are ready.' },
            { t: 'Straight to the dashboard', d: 'No setup call, no onboarding queue.' }].
            map((step, i) =>
            <li key={step.t} className="flex gap-4">
                <span className="mt-0.5 font-mono text-[12px] text-chalk-faint">0{i + 1}</span>
                <span>
                  <span className="block text-[15px] font-medium text-chalk">{step.t}</span>
                  <span className="mt-1 block text-[13.5px] leading-relaxed text-chalk-dim">{step.d}</span>
                </span>
              </li>
            )}
          </ol>
          <p className="mt-8 border-t border-ink-800 pt-6 text-[13px] leading-relaxed text-chalk-faint">
            You can change plans at any time from Settings — upgrades take effect immediately.
          </p>
        </aside>
      </div>
    </div>);

}