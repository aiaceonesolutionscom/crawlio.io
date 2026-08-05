import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckIcon, MinusIcon } from 'lucide-react';
import { Button } from '../../shared/ui/Button';
import { COMPARISON, PLANS } from '../../data/plans';
import { cn } from '../../shared/utils/cn';
import { useSession } from '../../contexts/SessionContext';
import type { PlanId } from '../../types';

export function Pricing() {
  const navigate = useNavigate();
  const { user, changePlan } = useSession();
  const [loading, setLoading] = useState<PlanId | null>(null);

  const handleSelect = async (plan: PlanId) => {
    if (user) {
      setLoading(plan);
      try {
        await changePlan(plan);
        navigate(`/app/${plan}`);
      } catch {
        navigate(`/app/${user.workspace.plan}`);
      } finally {
        setLoading(null);
      }
    } else {
      navigate('/signup');
    }
  };

  return (
    <section id="pricing" className="border-b border-ink-800 py-20 sm:py-28">
      <div className="mx-auto max-w-[1200px] px-5 sm:px-8">
        <div className="max-w-2xl">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-signal">Pricing</p>
          <h2 className="mt-4 font-display text-[32px] font-semibold leading-tight tracking-tight text-chalk sm:text-[42px]">
            Start free. Scale when the pipeline does.
          </h2>
          <p className="mt-4 text-[16px] leading-relaxed text-chalk-dim">
            Every plan includes AI qualification. What changes is volume, channels and control.
          </p>
        </div>

        <div className="mt-12 grid gap-5 lg:grid-cols-3">
          {PLANS.map((plan) => {
            const isCurrent = user?.workspace.plan === plan.id;
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
                  disabled={isCurrent || isLoading}
                  onClick={() => handleSelect(plan.id)}
                >
                  {isLoading ? 'Processing...' : isCurrent ? 'Current plan' : plan.cta}
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

        <div className="mt-14 overflow-x-auto scrollbar-slim">
          <table className="w-full min-w-[680px] border-collapse text-left">
            <caption className="sr-only">Feature comparison across Crawlio plans</caption>
            <thead>
              <tr className="border-b border-ink-700">
                <th scope="col" className="py-4 pr-4 font-mono text-[11px] uppercase tracking-[0.16em] text-chalk-faint">
                  Compare plans
                </th>
                {PLANS.map((plan) => (
                  <th
                    key={plan.id}
                    scope="col"
                    className={cn(
                      'py-4 px-4 font-display text-[15px] font-semibold tracking-tight',
                      plan.highlighted ? 'text-signal' : 'text-chalk'
                    )}
                  >
                    {plan.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {COMPARISON.map((group) => (
                <React.Fragment key={group.group}>
                  <tr>
                    <th
                      scope="colgroup"
                      colSpan={4}
                      className="pt-7 pb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-signal"
                    >
                      {group.group}
                    </th>
                  </tr>
                  {group.rows.map((row) => (
                    <tr key={row.label} className="border-b border-ink-850">
                      <th scope="row" className="py-3.5 pr-4 text-[14px] font-normal text-chalk-dim">
                        {row.label}
                      </th>
                      {PLANS.map((plan) => (
                        <td key={plan.id} className="px-4 py-3.5 text-[14px] text-chalk">
                          {row.values[plan.id]}
                        </td>
                      ))}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
