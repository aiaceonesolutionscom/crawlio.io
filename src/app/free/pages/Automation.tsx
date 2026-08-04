import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import { LockedFeatureCard } from '../components/LockedFeatureCard';

export function Automation() {
  const { openUpgrade } = useDashboardChrome();

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Automation Builder"
        description="Chain triggers, conditions and channel actions into a flow that works leads without a rep touching them." />

      <LockedFeatureCard
        title="Automation Builder is a Pro feature"
        description="Build multi-channel flows with conditions, delays and human handoff on Pro and above."
        onUpgrade={openUpgrade} />

    </div>);

}
