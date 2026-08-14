import React, { useState } from 'react';
import { UserPlusIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { LockedFeatureCard } from '../../../shared/ui/LockedFeatureCard';
import { TeamTable } from '../../../shared/team/TeamTable';
import { InviteMemberModal } from '../../../shared/team/InviteMemberModal';
import { useSession } from '../../../contexts/SessionContext';
import { useDashboardChrome } from '../../../shared/hooks/useDashboardChrome';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

export function Team({ tier }: Props) {
  const { user, refreshWorkspace } = useSession();
  const { openUpgrade } = useDashboardChrome();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  if (!user) return null;

  const handleInvited = () => {
    setRefreshKey((k) => k + 1);
    void refreshWorkspace();
  };

  if (tier === 'free') {
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

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Team"
        description="Invite teammates and set what each role can see and do inside this workspace."
        action={
        <Button onClick={() => setInviteOpen(true)}>
            <UserPlusIcon className="h-4 w-4" />
            Invite member
          </Button>
        } />

      <TeamTable refreshKey={refreshKey} tier={tier} />
      <InviteMemberModal open={inviteOpen} onClose={() => setInviteOpen(false)} onInvited={handleInvited} />
    </div>);

}