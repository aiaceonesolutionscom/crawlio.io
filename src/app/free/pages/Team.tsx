import React from 'react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import { LockedFeatureCard } from '../components/LockedFeatureCard';

export function Team() {
  const { openUpgrade } = useDashboardChrome();

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Team"
        description="Invite teammates and set what each role can see and do inside this workspace." />

      <LockedFeatureCard
        title="Team seats are a Pro feature"
        description="Free workspaces are single-seat. Pro includes 10 seats with Owner, Admin and Member roles."
        onUpgrade={openUpgrade} />

    </div>);

}
