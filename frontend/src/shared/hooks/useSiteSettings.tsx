import React, { createContext, useContext, useEffect, useState } from 'react';
import { apiFetch } from '../../lib/api/client';

interface SiteSettingDTO {
  id: string;
  key: string;
  value: unknown;
  value_type: string;
  description: string | null;
  updated_by: string | null;
  updated_at: string;
}

interface SiteSettingsContextValue {
  settings: {
    site_name: string;
    primary_color: string;
    secondary_color: string;
    hero_video_url: string;
    cta_text: string;
    feedback_text: string;
  };
  isLoaded: boolean;
}

const SiteSettingsContext = createContext<SiteSettingsContextValue | null>(null);

export function SiteSettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState({
    site_name: 'Crawlio',
    primary_color: '#CBFF4D',
    secondary_color: '#A9DE22',
    hero_video_url: '',
    cta_text: 'Get Started',
    feedback_text: 'Trusted by revenue teams worldwide',
  });
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    async function fetchSettings() {
      const token = localStorage.getItem('crawlio_admin_token');
      if (!token) {
        setIsLoaded(true);
        return;
      }
      try {
        const result = await apiFetch<SiteSettingDTO[]>('/api/v1/admin/system-settings', token);
        const settingsMap: Record<string, string> = {};

        result.forEach((s) => {
          if (s.value_type === 'string') {
            settingsMap[s.key] = String(s.value);
          } else if (s.value_type === 'color') {
            settingsMap[s.key] = String(s.value);
          } else if (s.value_type === 'url') {
            settingsMap[s.key] = String(s.value);
          } else if (s.value_type === 'boolean') {
            settingsMap[s.key] = String(s.value).toLowerCase() === 'true';
          } else if (s.value_type === 'json' && typeof s.value === 'object') {
            settingsMap[s.key] = JSON.stringify(s.value);
          }
        });

        setSettings({
          site_name: settingsMap.site_name || 'Crawlio',
          primary_color: settingsMap.primary_color || '#CBFF4D',
          secondary_color: settingsMap.secondary_color || '#A9DE22',
          hero_video_url: settingsMap.hero_video_url || '',
          cta_text: settingsMap.cta_text || 'Get Started',
          feedback_text: settingsMap.feedback_text || 'Trusted by revenue teams worldwide',
        });
        setIsLoaded(true);
      } catch (err) {
        console.error('Failed to fetch site settings', err);
        setIsLoaded(true);
      }
    }

    fetchSettings();

    // Poll for updates every 30 seconds
    const interval = setInterval(fetchSettings, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <SiteSettingsContext.Provider value={{ settings, isLoaded }}>{children}</SiteSettingsContext.Provider>
  );
}

export function useSiteSettings(): {
  settings: {
    site_name: string;
    primary_color: string;
    secondary_color: string;
    hero_video_url: string;
    cta_text: string;
    feedback_text: string;
  };
  isLoaded: boolean;
} {
  const ctx = useContext(SiteSettingsContext);
  if (!ctx) {
    throw new Error('useSiteSettings must be used within SiteSettingsProvider');
  }
  return ctx;
}