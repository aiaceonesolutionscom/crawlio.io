import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeftIcon } from 'lucide-react';
import { SignIn } from '@clerk/clerk-react';
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
  }
};

export function Login() {
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

        <div className="mt-8">
          <SignIn
            routing="path"
            path="/login"
            signUpUrl="/signup"
            fallbackRedirectUrl="/app"
            appearance={CLERK_APPEARANCE}
          />
        </div>
      </div>
    </div>
  );
}
