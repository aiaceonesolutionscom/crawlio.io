import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftIcon } from 'lucide-react';
import { SignUp } from '@clerk/clerk-react';
import { Logo } from '../shared/ui/Logo';

const CLERK_APPEARANCE = {
  variables: {
    colorPrimary: '#CBFF4D',
    colorBackground: '#131617',
    colorText: '#F1F4F0',
    colorTextSecondary: '#A5ADA7',
    colorInputBackground: '#191D1F',
    colorInputText: '#F1F4F0',
    borderRadius: '10px'
  },
  elements: {
    card: 'shadow-none bg-transparent',
    headerTitle: 'hidden',
    headerSubtitle: 'hidden',
    footer: 'hidden'
  }
};

export function Signup() {
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

          <div className="mt-8">
            <SignUp
              routing="path"
              path="/signup"
              signInUrl="/login"
              fallbackRedirectUrl="/app"
              appearance={CLERK_APPEARANCE} />

          </div>
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
            Every new workspace starts on Free. Plan selection at signup is coming back once workspace
            provisioning is wired up — for now you can upgrade from Settings after your first login.
          </p>
        </aside>
      </div>
    </div>);

}
