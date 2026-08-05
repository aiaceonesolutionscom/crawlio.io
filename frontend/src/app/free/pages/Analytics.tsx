import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import { LockedFeatureCard } from '../components/LockedFeatureCard';

export function Analytics() {
  const { openUpgrade } = useDashboardChrome();

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Analytics"
        description="Channel performance, source mix and reply quality across the whole workspace." />

      <LockedFeatureCard
        title="Analytics is a Pro feature"
        description="Full channel attribution and source reporting unlock on Pro and above."
        onUpgrade={openUpgrade} />

    </div>);

}
