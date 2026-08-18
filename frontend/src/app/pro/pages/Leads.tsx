import { LeadCenterPage } from '../../../shared/leads/LeadCenterPage';

export function Leads() {
  return (
    <LeadCenterPage
      tier="pro"
      searchEnabled
      whatsappEnabled
      bulkExportEnabled
      discoveryCap={50}
      discoveryEnhanced
      aiFilterEnabled />
  );
}
