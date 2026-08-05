import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';

export function Leads() {
  return (
    <LeadCenterPage
      tier="pro"
      searchEnabled
      whatsappEnabled
      discoveryCap={100}
      discoveryEnhanced />
  );
}
