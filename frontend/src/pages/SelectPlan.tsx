import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckIcon, MinusIcon } from 'lucide-react';
import { Button } from '../shared/ui/Button';
import { Logo } from '../shared/ui/Logo';
import { PLANS } from '../data/plans';
import { cn } from '../shared/utils/cn';
import { useSession } from '../contexts/SessionContext';
import type { PlanId } from '../types';

/** Mandatory post-signup step: a workspace exists on "free" the moment it's
 * created, but the owner hasn't confirmed a plan yet — RequirePlan/PlanRedirect
 * bounce here until they do, so /app can never be reached by accident. */
export function SelectPlan() {
  const navigate = useNavigate();
  const { user, changePlan, logout } = useSession();
  const [loading, setLoading] = useState<PlanId | null>(null);

  const handleSelect = async (plan: PlanId) => {
    setLoading(plan);
    try {
      await changePlan(plan);
      navigate(`/app/${plan}`, { replace: true });
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="min-h-screen w-full bg-ink-950">
      <header className="flex items-center justify-between border-b border-ink-800 px-5 py-5 sm:px-8">
        <Logo />
        <button
          type="button"
          onClick={() => logout()}
          className="text-[13px] text-chalk-faint transition-colors hover:text-chalk"
        >
          Log out
        </button>
      </header>

      <div className="mx-auto max-w-[1200px] px-5 py-16 sm:px-8 sm:py-20">
        <div className="max-w-2xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-signal">One last step</p>
          <h1 className="mt-4 font-display text-[32px] font-semibold leading-tight tracking-tight text-chalk sm:text-[42px]">
            {user ? `Welcome, ${user.name.split(' ')[0]} — pick your plan` : 'Pick your plan'}
          </h1>
          <p className="mt-4 text-[16px] leading-relaxed text-chalk-dim">
            Your workspace is ready. Choose a plan to continue — you can change it anytime from Settings.
          </p>
        </div>

        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {PLANS.map((plan) => {
            const isLoading = loading === plan.id;
            return (
              <article
                key={plan.id}
                className={cn(
                  'relative flex flex-col rounded-2xl border p-6 sm:p-7',
                  plan.highlighted
                    ? 'border-signal/60 bg-ink-850 shadow-[0_0_0_1px_rgba(203,255,77,0.18)]'
                    : 'border-ink-800 bg-ink-900'
                )}
              >
                {plan.highlighted && (
                  <span className="absolute -top-3 left-6 rounded-full bg-signal px-3 py-1 font-mono text-[10px] font-medium uppercase tracking-widest text-signal-deep">
                    Most popular
                  </span>
                )}

                <h3 className="font-display text-[20px] font-semibold tracking-tight text-chalk">{plan.name}</h3>
                <p className="mt-1.5 text-[14px] text-chalk-dim">{plan.tagline}</p>

                <div className="mt-6 flex items-baseline gap-1.5">
                  <span className="font-display text-[38px] font-semibold tracking-tightest text-chalk">
                    {plan.price}
                  </span>
                  {plan.id === 'pro' && <span className="text-[14px] text-chalk-faint">/mo</span>}
                </div>
                <p className="mt-1 text-[12.5px] text-chalk-faint">{plan.priceNote}</p>

                <Button
                  variant={plan.highlighted ? 'primary' : 'outline'}
                  className="mt-6 w-full"
                  disabled={loading !== null}
                  onClick={() => handleSelect(plan.id)}
                >
                  {isLoading ? 'Setting up...' : plan.cta}
                </Button>

                <p className="mt-5 border-t border-ink-800 pt-5 text-[13px] leading-relaxed text-chalk-dim">
                  {plan.bestFor}
                </p>

                <ul className="mt-5 space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature.label} className="flex items-start gap-2.5 text-[14px]">
                      {feature.included ? (
                        <CheckIcon className="mt-0.5 h-4 w-4 shrink-0 text-signal" aria-hidden="true" />
                      ) : (
                        <MinusIcon className="mt-0.5 h-4 w-4 shrink-0 text-ink-600" aria-hidden="true" />
                      )}
                      <span className={feature.included ? 'text-chalk-dim' : 'text-chalk-faint line-through'}>
                        {feature.label}
                      </span>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      </div>
    </div>
  );
}
