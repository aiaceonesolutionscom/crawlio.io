import React, { useEffect, useState } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { AnimatePresence, motion } from 'framer-motion';
import { CheckIcon, ClockIcon, Loader2Icon, MapPinIcon, SearchIcon, SparklesIcon, StarIcon, XIcon, ZapIcon } from 'lucide-react';
import { Button } from '../ui/Button';
import { cn } from '../utils/cn';
import { searchCountries, searchCities, type CountryDTO, type CityDTO } from '../../lib/api/geo';
import {
  discoverLeads,
  discoverStatus,
  importDiscoveredLeads,
  suggestNiches,
  type DiscoveredLeadDTO
} from '../../lib/api/discovery';
import { ApiError } from '../../lib/api/client';

const SOURCE_LABELS: Record<string, string> = {
  google_maps: 'Google Maps',
  openstreetmap: 'OpenStreetMap',
  directory: 'Directory'
};

interface Props {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
  onWantManualAdd: () => void;
  resultCap: number;
  enhancedTier: boolean;
}

export function LeadDiscoveryModal({
  open,
  onClose,
  onImported,
  onWantManualAdd,
  resultCap,
  enhancedTier
}: Props) {
  const { getToken } = useAuth();

  const [niche, setNiche] = useState('');
  const [nicheOptions, setNicheOptions] = useState<string[]>([]);
  const [nicheOpen, setNicheOpen] = useState(false);
  // Kept as a string so the field starts genuinely empty (not "0") and typing
  // a digit replaces it cleanly instead of the browser inserting alongside a
  // stray leading zero from a controlled numeric 0.
  const [desiredCountRaw, setDesiredCountRaw] = useState('');
  const desiredCount = desiredCountRaw === '' ? 0 : Math.min(Math.max(parseInt(desiredCountRaw, 10) || 0, 0), resultCap);

  const [countryQuery, setCountryQuery] = useState('');
  const [country, setCountry] = useState<CountryDTO | null>(null);
  const [countryOptions, setCountryOptions] = useState<CountryDTO[]>([]);
  const [countryOpen, setCountryOpen] = useState(false);

  const [cityQuery, setCityQuery] = useState('');
  const [city, setCity] = useState<CityDTO | null>(null);
  const [cityOptions, setCityOptions] = useState<CityDTO[]>([]);
  const [cityOpen, setCityOpen] = useState(false);

  const [isSearching, setIsSearching] = useState(false);
  const [searchId, setSearchId] = useState<string | null>(null);
  const [searchStage, setSearchStage] = useState('');
  const [searchError, setSearchError] = useState<string | null>(null);
  const [results, setResults] = useState<DiscoveredLeadDTO[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [enhanced, setEnhanced] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [dailyLimit, setDailyLimit] = useState<number | null>(null);
  const [remainingToday, setRemainingToday] = useState<number | null>(null);
  const [lastRequestedCount, setLastRequestedCount] = useState<number | null>(null);

  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importSummary, setImportSummary] = useState<string | null>(null);

  const reset = () => {
    setNiche('');
    setNicheOptions([]);
    setNicheOpen(false);
    setDesiredCountRaw('');
    setCountryQuery('');
    setCountry(null);
    setCountryOptions([]);
    setCountryOpen(false);
    setCityQuery('');
    setCity(null);
    setCityOptions([]);
    setCityOpen(false);
    setIsSearching(false);
    setSearchId(null);
    setSearchError(null);
    setResults([]);
    setSelected(new Set());
    setEnhanced(false);
    setHasSearched(false);
    setDailyLimit(null);
    setRemainingToday(null);
    setLastRequestedCount(null);
    setIsImporting(false);
    setImportError(null);
    setImportSummary(null);
  };

  const handleClose = () => {
    reset();
    onClose();
  };

  useEffect(() => {
    if (!open) return;
    const timeout = window.setTimeout(async () => {
      const token = await getToken();
      const res = await suggestNiches(token, niche || undefined);
      setNicheOptions(res.items);
    }, 150);
    return () => window.clearTimeout(timeout);
  }, [niche, open, getToken]);

  useEffect(() => {
    if (!open || country) return;
    const timeout = window.setTimeout(async () => {
      const token = await getToken();
      const res = await searchCountries(token, countryQuery || undefined);
      setCountryOptions(res.items);
    }, 150);
    return () => window.clearTimeout(timeout);
  }, [countryQuery, open, country, getToken]);

  useEffect(() => {
    if (!open || !country || city || cityQuery.trim().length < 2) {
      setCityOptions([]);
      return;
    }
    const timeout = window.setTimeout(async () => {
      const token = await getToken();
      const res = await searchCities(token, country.code, cityQuery);
      setCityOptions(res.items);
    }, 300);
    return () => window.clearTimeout(timeout);
  }, [cityQuery, country, city, open, getToken]);

  // Discovery runs in the background server-side (the POST returns a search_id
  // instantly), so while the crawl is live we poll the status endpoint for
  // results and keep the honest progress text cycling until items land.
  useEffect(() => {
    if (!isSearching) {
      setSearchStage('');
      return;
    }
    const stages = enhancedTier
      ? [
          'Searching the web for businesses…',
          'Searching business directories with AI…',
          'Checking business websites for contact info…',
          'Looking up social profiles with AI…',
          'Still working — some searches take a little longer…'
        ]
      : [
          'Searching the web for businesses…',
          'Checking business websites for contact info…',
          'Filtering out incomplete listings…',
          'Still working — some searches take a little longer…'
        ];
    let i = 0;
    setSearchStage(stages[0]);
    const interval = window.setInterval(() => {
      i = Math.min(i + 1, stages.length - 1);
      setSearchStage(stages[i]);
    }, 3500);
    return () => window.clearInterval(interval);
  }, [isSearching, enhancedTier]);

  useEffect(() => {
    if (!searchId || !open) return;
    let cancelled = false;
    let timer: number | undefined;
    let attempts = 0;
    let polls = 0;

    const poll = async () => {
      try {
        const token = await getToken();
        const res = await discoverStatus(token, searchId);
        if (cancelled) return;
        if (res.status === 'failed') {
          setSearchError('The search could not complete. Please try again.');
          setResults([]);
          setSearchId(null);
          setIsSearching(false);
          return;
        }
        if (res.items.length > 0 || res.status === 'done') {
          setResults(res.items);
          setSelected(new Set(res.items.map((_, i) => i).filter((i) => !res.items[i].already_in_workspace)));
          setSearchId(null);
          setIsSearching(false);
          return;
        }
        polls += 1;
        if (polls >= 240) {
          setSearchError('The search took too long and was stopped. Please try a smaller count or try again.');
          setResults([]);
          setSearchId(null);
          setIsSearching(false);
          return;
        }
        timer = window.setTimeout(() => void poll(), 2500);
      } catch (err) {
        if (cancelled) return;
        attempts += 1;
        if (attempts >= 8) {
          setSearchError(err instanceof ApiError ? err.message : 'Could not reach the search service. Please try again.');
          setResults([]);
          setSearchId(null);
          setIsSearching(false);
          return;
        }
        timer = window.setTimeout(() => void poll(), 2500);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [searchId, open, getToken]);

  const canSearch =
    niche.trim().length > 0 &&
    (country !== null || countryQuery.trim().length > 0) &&
    (city !== null || cityQuery.trim().length > 0) &&
    desiredCount > 0 &&
    !isSearching;

  const handleSearch = async () => {
    if (!niche.trim()) return;
    setIsSearching(true);
    setSearchError(null);
    setHasSearched(true);
    setImportSummary(null);
    try {
      const token = await getToken();

      // Selecting a suggestion from the dropdown is the normal path, but if the
      // user just typed a name and hit Search without clicking a suggestion
      // (easy to do, and previously left Search silently disabled forever),
      // resolve it here instead of blocking them.
      let resolvedCountry = country;
      if (!resolvedCountry) {
        if (!countryQuery.trim()) {
          setSearchError('Pick a country.');
          setIsSearching(false);
          return;
        }
        const countryRes = await searchCountries(token, countryQuery.trim());
        resolvedCountry = countryRes.items[0] ?? null;
        if (!resolvedCountry) {
          setSearchError(`No country matches "${countryQuery}". Try a different spelling.`);
          setIsSearching(false);
          return;
        }
        setCountry(resolvedCountry);
        setCountryQuery('');
      }

      let resolvedCity = city;
      if (!resolvedCity) {
        if (!cityQuery.trim()) {
          setSearchError('Pick a city.');
          setIsSearching(false);
          return;
        }
        const cityRes = await searchCities(token, resolvedCountry.code, cityQuery.trim());
        resolvedCity = cityRes.items[0] ?? null;
        if (!resolvedCity) {
          setSearchError(`No city matches "${cityQuery}" in ${resolvedCountry.name}. Try a different spelling.`);
          setIsSearching(false);
          return;
        }
        setCity(resolvedCity);
        setCityQuery('');
      }

      const requestedCount = Math.min(Math.max(desiredCount, 1), resultCap);
      const res = await discoverLeads(token, {
        niche: niche.trim(),
        country: resolvedCountry.code,
        city: resolvedCity.name,
        lat: resolvedCity.lat,
        lon: resolvedCity.lon,
        limit: requestedCount
      });
      setLastRequestedCount(requestedCount);
      setEnhanced(res.enhanced);
      setDailyLimit(res.daily_limit);
      setRemainingToday(res.remaining_today);
      if (res.search_id) {
        // Crawl runs in the background — keep "searching" state on and let the
        // polling effect surface results when the status endpoint has them.
        setSearchId(res.search_id);
        return;
      }
      setResults(res.items);
      // Pre-select only what's actually new — an already-in-CRM lead would
      // just be silently skipped as a duplicate on import anyway, so leaving
      // it checked by default makes a repeat search look like nothing changed.
      setSelected(new Set(res.items.map((_, i) => i).filter((i) => !res.items[i].already_in_workspace)));
      setIsSearching(false);
    } catch (err) {
      setSearchError(err instanceof ApiError ? err.message : 'Search failed. Please try again.');
      setResults([]);
      setIsSearching(false);
    }
  };

  const toggleSelected = (index: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  const toggleAll = () => {
    setSelected((prev) => (prev.size === results.length ? new Set() : new Set(results.map((_, i) => i))));
  };

  const handleImport = async () => {
    const items = results.filter((_, i) => selected.has(i));
    if (items.length === 0) return;
    setIsImporting(true);
    setImportError(null);
    try {
      const token = await getToken();
      const res = await importDiscoveredLeads(token, items);
      const dailyCapped = res.skipped.filter((s) => s.reason === 'daily_limit_reached').length;
      const otherSkipped = res.skipped.length - dailyCapped;
      const parts = [`${res.created.length} lead${res.created.length === 1 ? '' : 's'} added`];
      if (dailyCapped) parts.push(`${dailyCapped} hit today's daily limit`);
      if (otherSkipped) parts.push(`${otherSkipped} skipped (duplicate or quota reached)`);
      setImportSummary(parts.join(', '));
      if (remainingToday !== null) {
        setRemainingToday(Math.max(remainingToday - res.created.length, 0));
      }
      setResults((prev) => prev.filter((_, i) => !selected.has(i)));
      setSelected(new Set());
      onImported();
    } catch (err) {
      setImportError(err instanceof ApiError ? err.message : 'Import failed. Please try again.');
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[60] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.button
            type="button"
            aria-label="Close"
            onClick={handleClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-ink-950/85 backdrop-blur-sm"
          />

          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="discover-leads-title"
            initial={{ opacity: 0, y: 24, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.98 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative flex max-h-[88vh] w-full max-w-[720px] flex-col overflow-hidden rounded-t-2xl border border-ink-700 bg-ink-900 sm:rounded-2xl"
          >
            <div className="flex items-start justify-between gap-4 border-b border-ink-850 px-6 py-5">
              <div>
                <h2 id="discover-leads-title" className="font-display text-[18px] font-semibold tracking-tight text-chalk">
                  Find leads
                </h2>
                <p className="mt-1 text-[13px] text-chalk-dim">
                  Search real businesses by niche and location, then add the ones you want.
                </p>
              </div>
              <button
                type="button"
                onClick={handleClose}
                aria-label="Close dialog"
                className="rounded-lg p-1.5 text-chalk-faint hover:bg-ink-850 hover:text-chalk"
              >
                <XIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="flex flex-col gap-4 overflow-y-auto px-6 py-5 scrollbar-slim">
              <div className="grid gap-3 sm:grid-cols-4">
                <div className="relative">
                  <label htmlFor="discover-niche" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                    Niche
                  </label>
                  <input
                    id="discover-niche"
                    value={niche}
                    onChange={(e) => setNiche(e.target.value)}
                    onFocus={() => setNicheOpen(true)}
                    onBlur={() => window.setTimeout(() => setNicheOpen(false), 120)}
                    placeholder="Dental clinic, restaurant, salon…"
                    autoComplete="off"
                    className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                  />
                  {nicheOpen && nicheOptions.length > 0 && (
                    <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-ink-700 bg-ink-850 py-1 shadow-xl scrollbar-slim">
                      {nicheOptions.map((n) => (
                        <li key={n}>
                          <button
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              setNiche(n);
                              setNicheOpen(false);
                            }}
                            className="block w-full px-3.5 py-2 text-left text-[13.5px] text-chalk hover:bg-ink-800"
                          >
                            {n}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="relative">
                  <label htmlFor="discover-country" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                    Country
                  </label>
                  <input
                    id="discover-country"
                    value={country ? country.name : countryQuery}
                    onChange={(e) => {
                      setCountry(null);
                      setCountryQuery(e.target.value);
                      setCountryOpen(true);
                    }}
                    onFocus={() => setCountryOpen(true)}
                    onBlur={() => window.setTimeout(() => setCountryOpen(false), 120)}
                    placeholder="Pakistan, USA…"
                    autoComplete="off"
                    className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                  />
                  {countryOpen && !country && countryOptions.length > 0 && (
                    <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-ink-700 bg-ink-850 py-1 shadow-xl scrollbar-slim">
                      {countryOptions.map((c) => (
                        <li key={c.code}>
                          <button
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              setCountry(c);
                              setCountryQuery('');
                              setCountryOpen(false);
                              setCity(null);
                              setCityQuery('');
                            }}
                            className="block w-full px-3.5 py-2 text-left text-[13.5px] text-chalk hover:bg-ink-800"
                          >
                            {c.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div className="relative">
                  <label htmlFor="discover-city" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                    City
                  </label>
                  <input
                    id="discover-city"
                    value={city ? city.name : cityQuery}
                    onChange={(e) => {
                      setCity(null);
                      setCityQuery(e.target.value);
                      setCityOpen(true);
                    }}
                    onFocus={() => setCityOpen(true)}
                    onBlur={() => window.setTimeout(() => setCityOpen(false), 120)}
                    disabled={!country}
                    placeholder={country ? 'Karachi, Lahore…' : 'Pick a country first'}
                    autoComplete="off"
                    className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none disabled:cursor-not-allowed disabled:opacity-55"
                  />
                  {cityOpen && !city && cityOptions.length > 0 && (
                    <ul className="absolute z-10 mt-1 max-h-56 w-full overflow-y-auto rounded-lg border border-ink-700 bg-ink-850 py-1 shadow-xl scrollbar-slim">
                      {cityOptions.map((c) => (
                        <li key={`${c.name}-${c.lat}`}>
                          <button
                            type="button"
                            onMouseDown={(e) => e.preventDefault()}
                            onClick={() => {
                              setCity(c);
                              setCityQuery('');
                              setCityOpen(false);
                            }}
                            className="block w-full px-3.5 py-2 text-left text-[13.5px] text-chalk hover:bg-ink-800"
                          >
                            {c.name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>

                <div>
                  <label htmlFor="discover-count" className="mb-1.5 block text-[13px] font-medium text-chalk-dim">
                    How many
                  </label>
                  <input
                    id="discover-count"
                    type="number"
                    min={0}
                    max={resultCap}
                    value={desiredCountRaw}
                    onChange={(e) => setDesiredCountRaw(e.target.value.replace(/[^\d]/g, ''))}
                    onBlur={() => {
                      if (desiredCountRaw === '') return;
                      setDesiredCountRaw(String(Math.min(Math.max(parseInt(desiredCountRaw, 10) || 0, 0), resultCap)));
                    }}
                    placeholder="Add number of leads"
                    className="h-11 w-full rounded-lg border border-ink-700 bg-ink-950 px-3.5 text-[14px] text-chalk placeholder:text-chalk-faint focus:border-signal focus:outline-none"
                  />
                </div>
              </div>

              {desiredCount === 0 ? (
                <div className="flex flex-col gap-3 rounded-lg border border-ink-800 bg-ink-850/40 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-[12.5px] text-chalk-faint">
                    Looking for a specific business you already know? Search isn't useful with 0 results — add it
                    directly instead.
                  </p>
                  <Button size="sm" variant="outline" onClick={onWantManualAdd}>
                    Add lead manually
                  </Button>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <p className={cn('text-[12.5px]', isSearching ? 'text-signal' : 'text-chalk-faint')}>
                    {isSearching ? (
                      searchStage
                    ) : (
                      <>
                        Up to {resultCap} results per search
                        {enhancedTier ? ' · enhanced with AI-assisted contact lookup' : ''}.
                        {remainingToday !== null && dailyLimit !== null && (
                          <> {remainingToday} of {dailyLimit} adds left today.</>
                        )}
                      </>
                    )}
                  </p>
                  <Button size="sm" disabled={!canSearch} onClick={() => void handleSearch()}>
                    {isSearching ? <Loader2Icon className="h-4 w-4 animate-spin" /> : <SearchIcon className="h-4 w-4" />}
                    {isSearching ? 'Searching…' : 'Search'}
                  </Button>
                </div>
              )}

              {searchError && (
                <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {searchError}
                </p>
              )}
              {importError && (
                <p role="alert" className="rounded-lg border border-ember/40 bg-ember/10 px-3.5 py-2.5 text-[13px] text-ember">
                  {importError}
                </p>
              )}
              {importSummary && (
                <p className="rounded-lg border border-signal/40 bg-signal/10 px-3.5 py-2.5 text-[13px] text-signal">
                  {importSummary}
                </p>
              )}

              {hasSearched && !isSearching && !searchError && (
                <div className="overflow-hidden rounded-xl border border-ink-800">
                  <div className="flex items-center justify-between border-b border-ink-800 bg-ink-850/60 px-4 py-2.5">
                    <label className="flex items-center gap-2 text-[12.5px] text-chalk-dim">
                      <input
                        type="checkbox"
                        checked={results.length > 0 && selected.size === results.length}
                        onChange={toggleAll}
                        className="h-3.5 w-3.5 rounded border-ink-600 bg-ink-950 accent-signal"
                      />
                      {results.length} found · {selected.size} selected
                    </label>
                    {enhanced && (
                      <span className="flex items-center gap-1 text-[11px] text-signal">
                        <SparklesIcon className="h-3 w-3" /> Enhanced
                      </span>
                    )}
                  </div>

                  {results.length > 0 && lastRequestedCount !== null && results.length < lastRequestedCount && (
                    <p className="border-b border-ink-800 bg-ink-850/40 px-4 py-2 text-[12px] text-chalk-faint">
                      You asked for {lastRequestedCount}, but we only found {results.length} real{' '}
                      {niche.trim()} listings with contact info for this area — that's all of what exists there,
                      not a limit on our side.
                    </p>
                  )}

                  {results.length === 0 ? (
                    <p className="px-4 py-8 text-center text-[13.5px] text-chalk-dim">
                      No businesses found for that niche and city. Try a broader niche term or a larger nearby city.
                    </p>
                  ) : (
                    <ul className="max-h-72 divide-y divide-ink-850 overflow-y-auto scrollbar-slim">
                      {results.map((r, i) => (
                        <li key={`${r.name}-${i}`} className="flex items-start gap-3 px-4 py-3">
                          <button
                            type="button"
                            onClick={() => toggleSelected(i)}
                            aria-pressed={selected.has(i)}
                            className={cn(
                              'mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded border',
                              selected.has(i) ? 'border-signal bg-signal text-signal-deep' : 'border-ink-600'
                            )}
                          >
                            {selected.has(i) && <CheckIcon className="h-3 w-3" />}
                          </button>
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="truncate text-[13.5px] font-medium text-chalk">{r.name}</p>
                              {r.industry && (
                                <span className="shrink-0 rounded-full border border-ink-700 px-2 py-0.5 text-[10.5px] text-chalk-faint">
                                  {r.industry}
                                </span>
                              )}
                              {r.rating != null && (
                                <span className="flex shrink-0 items-center gap-1 text-[11px] text-chalk-dim">
                                  <StarIcon className="h-3 w-3 fill-amber-400 text-amber-400" />
                                  {r.rating.toFixed(1)}
                                  {r.review_count != null && (
                                    <span className="text-chalk-faint">({r.review_count})</span>
                                  )}
                                </span>
                              )}
                              {SOURCE_LABELS[r.source] && (
                                <span className="shrink-0 rounded-full border border-ink-700 px-2 py-0.5 text-[10.5px] text-chalk-faint">
                                  {SOURCE_LABELS[r.source]}
                                </span>
                              )}
                              {r.cache_hit && (
                                <span className="flex shrink-0 items-center gap-1 rounded-full border border-signal/40 px-2 py-0.5 text-[10.5px] text-signal">
                                  <ZapIcon className="h-2.5 w-2.5" />
                                  Cached
                                </span>
                              )}
                              {r.is_fallback_city && r.result_city && (
                                <span className="flex shrink-0 items-center gap-1 rounded-full border border-ink-700 px-2 py-0.5 text-[10.5px] text-chalk-faint">
                                  <MapPinIcon className="h-2.5 w-2.5" />
                                  Nearby: {r.result_city}
                                </span>
                              )}
                              {r.already_in_workspace && (
                                <span className="shrink-0 rounded-full border border-ink-700 px-2 py-0.5 text-[10.5px] text-chalk-faint">
                                  Already in your CRM
                                </span>
                              )}
                            </div>
                            <p className="truncate text-[12px] text-chalk-faint">
                              {[r.address, r.phone, r.email].filter(Boolean).join(' · ') || 'No contact details found'}
                            </p>
                            {r.hours && (
                              <p className="mt-0.5 flex items-center gap-1 truncate text-[11.5px] text-chalk-faint">
                                <ClockIcon className="h-3 w-3 shrink-0" />
                                {r.hours}
                              </p>
                            )}
                            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1">
                              {r.website && (
                                <a
                                  href={r.website}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="truncate text-[12px] text-signal hover:underline"
                                >
                                  {r.website}
                                </a>
                              )}
                              {Object.entries(r.social_links ?? {}).map(([platform, url]) => (
                                <a
                                  key={platform}
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="truncate text-[12px] capitalize text-signal hover:underline"
                                >
                                  {platform}
                                </a>
                              ))}
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-2 border-t border-ink-850 px-6 py-4">
              <Button type="button" variant="outline" onClick={handleClose}>
                Close
              </Button>
              <Button type="button" disabled={selected.size === 0 || isImporting} onClick={() => void handleImport()}>
                {isImporting && <Loader2Icon className="h-4 w-4 animate-spin" />}
                {isImporting ? 'Adding…' : `Add selected (${selected.size})`}
              </Button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
