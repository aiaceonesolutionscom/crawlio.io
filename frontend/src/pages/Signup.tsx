import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftIcon } from 'lucide-react';
import { SignUp } from '@clerk/clerk-react';
import { Logo } from '../shared/ui/Logo';

const CLERK_APPEARANCE = {
  variables: {
    colorPrimary: '#CBFF4D',
    colorPrimaryHover: '#A9DE22',
    colorBackground: '#131617',
    colorText: '#F1F4F0',
    colorTextSecondary: '#A5ADA7',
    colorInputBackground: '#191D1F',
    colorInputText: '#F1F4F0',
    colorTextOnPrimaryBackground: '#141A05',
    borderRadius: '10px',
  },
  elements: {
    card: 'shadow-none bg-transparent',
    socialButtonsBlockButton: 'border border-ink-700 bg-ink-900 hover:bg-ink-850 text-chalk rounded-lg',
    socialButtonsBlockButtonText: 'text-chalk font-medium text-[14px]',
    formFieldLabel: 'text-chalk-dim text-[13px] font-medium',
    formFieldInput: 'bg-ink-800 border border-ink-700 text-chalk rounded-lg h-11 px-4 text-[15px] focus:border-signal focus:ring-1 focus:ring-signal/30',
    formButtonPrimary: 'bg-signal text-signal-deep hover:bg-signal-dark rounded-lg h-12 text-[15px] font-semibold transition-colors',
    footerActionLink: 'text-signal hover:text-signal-dark',
    dividerLine: 'bg-ink-700',
    dividerText: 'text-chalk-faint bg-ink-950',
    formFieldErrorText: 'text-red-400',
    footer: '[&>*]:hidden',
    brandedShine: 'hidden',
    badge: 'hidden',
    logoImage: 'hidden',
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
              appearance={CLERK_APPEARANCE}
            />
          </div>
        </div>

        <aside className="hidden rounded-2xl border border-ink-800 bg-ink-900 p-7 lg:block">
          <h2 className="font-mono text-[11px] uppercase tracking-[0.16em] text-signal">What happens next</h2>
          <ol className="mt-6 space-y-6">
            {[
              { t: 'Workspace created', d: 'Isolated tenant with your own data boundary and owner role.' },
              { t: 'Pick your plan', d: 'Choose Free, Pro or Enterprise from the pricing section — change anytime.' },
              { t: 'Defaults seeded', d: 'A sample campaign, scoring model and starter dashboard are ready.' },
              { t: 'Straight to the dashboard', d: 'No setup call, no onboarding queue.' },
            ].map((step, i) => (
              <li key={step.t} className="flex gap-4">
                <span className="mt-0.5 font-mono text-[12px] text-chalk-faint">0{i + 1}</span>
                <span>
                  <span className="block text-[15px] font-medium text-chalk">{step.t}</span>
                  <span className="mt-1 block text-[13.5px] leading-relaxed text-chalk-dim">{step.d}</span>
                </span>
              </li>
            ))}
          </ol>
          <p className="mt-8 border-t border-ink-800 pt-6 text-[13px] leading-relaxed text-chalk-faint">
            Every new workspace starts on Free. After signup you&apos;ll be taken to the pricing page
            where you can select the plan that fits your pipeline.
          </p>
        </aside>
      </div>
    </div>
  );
}
