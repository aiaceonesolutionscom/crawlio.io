import React, { useState } from 'react';
import { UserPlusIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { useSession } from '../../../contexts/SessionContext';
import { TeamTable } from '../components/TeamTable';
import { InviteMemberModal } from '../components/InviteMemberModal';

export function Team() {
  const { user, refreshWorkspace } = useSession();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [refreshKey, setRefreshKey] = useState(0);
  if (!user) return null;

  const handleInvited = () => {
    setRefreshKey((k) => k + 1);
    void refreshWorkspace();
  };

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


      <TeamTable refreshKey={refreshKey} />

      <InviteMemberModal open={inviteOpen} onClose={() => setInviteOpen(false)} onInvited={handleInvited} />
    </div>);

}
