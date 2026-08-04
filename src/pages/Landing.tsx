import React from 'react';
import { SiteHeader } from '../components/landing/SiteHeader';
import { Hero } from '../components/landing/Hero';
import { Features } from '../components/landing/Features';
import { Pricing } from '../components/landing/Pricing';
import { Testimonials } from '../components/landing/Testimonials';
import { FAQ } from '../components/landing/FAQ';
import { SiteFooter } from '../components/landing/SiteFooter';

export function Landing() {
  return (
    <div className="w-full bg-ink-950">
      <SiteHeader />
      <main>
        <Hero />
        <Features />
        <Pricing />
        <Testimonials />
        <FAQ />
      </main>
      <SiteFooter />
    </div>);

}