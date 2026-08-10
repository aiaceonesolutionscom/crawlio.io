import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { MenuIcon, XIcon } from 'lucide-react';
import { SignedIn, SignedOut } from '@clerk/clerk-react';
import { ButtonLink } from '../../shared/ui/Button';
import { Logo } from '../../shared/ui/Logo';

const NAV = [
{ label: 'Product', href: '#product' },
{ label: 'How it works', href: '#pipeline' },
{ label: 'Pricing', href: '#pricing' },
{ label: 'FAQ', href: '#faq' }];


export function SiteHeader() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b border-ink-800/80 bg-ink-950/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 w-full max-w-[1200px] items-center justify-between px-5 sm:px-8">
        <Link to="/" className="flex items-center gap-2.5" aria-label="Crawlio home">
          <Logo />
        </Link>

        <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
          {NAV.map((item) =>
          <a
            key={item.label}
            href={item.href}
            className="rounded-md px-3 py-2 text-sm text-chalk-dim transition-colors hover:text-chalk">
            
              {item.label}
            </a>
          )}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <SignedOut>
            <ButtonLink to="/login" variant="ghost" size="sm">
              Login
            </ButtonLink>
            <ButtonLink to="/signup" size="sm">
              Get started
            </ButtonLink>
          </SignedOut>
          <SignedIn>
            <ButtonLink to="/app" size="sm">
              Go to dashboard
            </ButtonLink>
          </SignedIn>
        </div>

        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg border border-ink-700 text-chalk md:hidden"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}>
          
          {open ? <XIcon className="h-5 w-5" /> : <MenuIcon className="h-5 w-5" />}
        </button>
      </div>

      {open &&
      <div className="border-t border-ink-800 bg-ink-950 px-5 pb-5 pt-3 md:hidden">
          <nav aria-label="Mobile" className="flex flex-col">
            {NAV.map((item) =>
          <a
            key={item.label}
            href={item.href}
            onClick={() => setOpen(false)}
            className="border-b border-ink-850 py-3 text-[15px] text-chalk-dim">
            
                {item.label}
              </a>
          )}
          </nav>
          <div className="mt-4 flex flex-col gap-2">
            <SignedOut>
              <ButtonLink to="/login" variant="outline">
                Login
              </ButtonLink>
              <ButtonLink to="/signup">Get started — it&rsquo;s free</ButtonLink>
            </SignedOut>
            <SignedIn>
              <ButtonLink to="/app">Go to dashboard</ButtonLink>
            </SignedIn>
          </div>
        </div>
      }
    </header>);

}