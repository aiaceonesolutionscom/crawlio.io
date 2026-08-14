import { EmailAgentPage } from '../../../shared/automation/email/EmailAgentPage';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

export function EmailAgent({ tier }: Props) {
  return <EmailAgentPage backTo={`/app/${tier}/automation`} />;
}