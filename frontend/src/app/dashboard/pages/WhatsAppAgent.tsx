import { WhatsAppAgentPage } from '../../../shared/automation/WhatsAppAgentPage';
import type { PlanId } from '../../../types';

interface Props {
  tier: PlanId;
}

export function WhatsAppAgent({ tier }: Props) {
  return <WhatsAppAgentPage backTo={`/app/${tier}/automation`} />;
}
