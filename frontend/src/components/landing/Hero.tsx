import { useState } from 'react';
import { useSystemSettings } from '../lib/api/systemSettings';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowRightIcon, PlayIcon, SparklesIcon } from 'lucide-react';
import { SignedOut } from '@clerk/clerk-react';
import { Button, ButtonLink } from '../../shared/ui/Button';
import { HeroBackdrop } from './HeroBackdrop';
import { useSiteSettings } from '../../shared/hooks/useSiteSettings';

const fade = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.55, delay: 0.06 * i, ease: [0.22, 1, 0.36, 1] as const }
  })
};

export function Hero({ ctaText, primaryColor }: { ctaText?: string; primaryColor?: string }) {
  const [email, setEmail] = useState('');
  const navigate = useNavigate();
  const { settings } = useSiteSettings();

  const effectivePrimaryColor = primaryColor || settings?.primary_color || '#CBFF4D';
  const effectiveCtaText = ctaText || settings?.cta_text || 'Get Started';

  return (
    <section className="relative isolate overflow-hidden border-b border-ink-800">
      <HeroBackdrop />

      <div className="relative mx-auto w-full max-w-[1200px] px-5 pb-20 pt-20 sm:px-8 sm:pb-28 sm:pt-28">
        <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_0.95fr]">
          <div>
            <motion.div variants={fade} custom={0} initial="hidden" animate="show">
              <span className="inline-flex items-center gap-2 rounded-full border border-ink-700 bg-ink-900/70 px-3 py-1.5 text-[12px] font-medium text-chalk-dim">
                <SparklesIcon className="h-3.5 w-3.5 text-signal" />
                AI lead automation, live in under 10 minutes
              </span>
            </motion.div>

            <motion.h1
              variants={fade}
              custom={1}
              initial="hidden"
              animate="show"
              className="mt-6 font-display text-[42px] font-semibold leading-[1.02] tracking-tightest text-chalk sm:text-[62px] lg:text-[68px]">
              
              Capture. Qualify.
              <br />
              Automate. <span className="text-signal">Close.</span>
            </motion.h1>

            <motion.p
              variants={fade}
              custom={2}
              initial="hidden"
              animate="show"
              className="mt-6 max-w-xl text-[17px] leading-relaxed text-chalk-dim">
              
              Crawlio is the AI-powered lead automation platform for revenue teams. It pulls in every lead,
              scores it against your best customers, and runs email and WhatsApp follow-up until a human is
              actually needed.
            </motion.p>

            <motion.form
              variants={fade}
              custom={3}
              initial="hidden"
              animate="show"
              onSubmit={(e) => {
                e.preventDefault();
                navigate('/signup', { state: { email } });
              }}
              className="mt-9 flex flex-col gap-3 sm:flex-row">
                
                <label htmlFor="hero-email" className="sr-only">
                  Work email
                </label>
                <input
                  id="hero-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  className="h-[52px] w-full rounded-lg border border-ink-700 bg-ink-900/80 px-4 text-[15px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none sm:max-w-[300px]" />
                
                <Button type="submit" size="lg">
                  {effectiveCtaText}
                  <ArrowRightIcon className="h-4 w-4" />
                </Button>
              </motion.form>

              <motion.div
                variants={fade}
                custom={4}
                initial="hidden"
                animate="show"
                className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13px] text-chalk-faint">
                
                <span>700 leads/month free</span>
                <span aria-hidden="true">·</span>
                <span>No credit card</span>
                <span aria-hidden="true">·</span>
                <SignedOut>
                  <ButtonLink to="/login" variant="ghost" size="sm" className="-ml-3.5">
                    Already have an account? Login
                  </ButtonLink>
                </SignedOut>
              </motion.div>
          </div>

          {/* Demo video slot */}
          <motion.div
            initial={{ opacity: 0, scale: 0.97 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.7, delay: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative">
            
            <div className="relative aspect-video w-full overflow-hidden rounded-2xl border border-ink-700 bg-ink-900">
              <div className="grid-backdrop absolute inset-0 opacity-40" />
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-4">
                <span className="relative flex h-16 w-16 items-center justify-center rounded-full bg-signal text-signal-deep">
                  <span className="absolute inset-0 rounded-full bg-signal/40 animate-pulse-ring" aria-hidden="true" />
                  <PlayIcon className="h-6 w-6 translate-x-[1px]" fill="currentColor" />
                </span>
                <div className="text-center">
                  <p className="font-display text-[15px] font-semibold text-chalk">Demo Video</p>
                  <p className="mt-1 font-mono text-[11px] uppercase tracking-widest text-chalk-faint">
                    2:14 — product walkthrough
                  </p>
                </div>
              </div>
              <div className="absolute inset-x-0 bottom-0 flex items-center gap-3 border-t border-ink-800 bg-ink-950/70 px-4 py-3">
                <span className="h-1.5 w-1.5 rounded-full bg-signal" aria-hidden="true" />
                <span className="text-[12px] text-chalk-dim">Capture → Qualify → Automate → Close</span>
              </div>
              <p className="mt-3 text-center text-[12px] text-chalk-faint">
                Placeholder — embed replaces this block.
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>);
}
