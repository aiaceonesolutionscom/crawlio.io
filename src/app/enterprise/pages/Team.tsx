import React from 'react';
import { UserPlusIcon } from 'lucide-react';
import { PageHeader } from '../../../shared/layout/PageHeader';
import { Button } from '../../../shared/ui/Button';
import { useAuth } from '../../../contexts/AuthContext';
import { TeamTable } from '../components/TeamTable';

export function Team() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <div className="mx-auto w-full max-w-[1180px]">
      <PageHeader
        title="Team"
        description="Invite teammates and set what each role can see and do inside this workspace."
        action={
        <Button>
            <UserPlusIcon className="h-4 w-4" />
            Invite member
          </Button>
        } />


      <TeamTable workspace={user.workspace} />
    </div>);

}
