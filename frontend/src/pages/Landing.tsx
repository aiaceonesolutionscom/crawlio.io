import React from 'react';
import { SiteHeader } from '../components/landing/SiteHeader';
import { Hero } from '../components/landing/Hero';
import { Features } from '../components/landing/Features';
import { Pricing } from '../components/landing/Pricing';
import { Testimonials } from '../components/landing/Testimonials';
import { FAQ } from '../components/landing/FAQ';
import { SiteFooter } from '../components/landing/SiteFooter';
import { useSiteSettings } from '../shared/hooks/useSiteSettings';

export function Landing() {
  const { settings } = useSiteSettings();

  return (
    <div className="w-full bg-ink-950">
      <SiteHeader primaryColor={settings.primary_color} />
      <main>
        <Hero ctaText={settings.cta_text} primaryColor={settings.primary_color} />
        <Features />
        <Pricing />
        <Testimonials />
        <FAQ />
      </main>
      <SiteFooter />
    </div>);
}