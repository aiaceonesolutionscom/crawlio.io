"""DNS discovery crawler.

Enumerates DNS records (A, AAAA, MX, TXT, CNAME) for domains associated with
a given niche and location. This can reveal subdomains, mail servers, and
other hostnames that may correspond to businesses or services.

Uses the `dns` module (dnspython) for robust record queries. If dnspython
is not available, a simple `asyncio.create_subprocess_exec` fallback via
`nslookup`/`dig` is used.
"""
import asyncio
import logging
from typing import Optional

import aiohttp

try:
    import dns.resolver
    HAS_DNSPYTHON = True
except ImportError:
    HAS_DNSPYTHON = False

logger = logging.getLogger(__name__)

# Common DNS record types to query.
_DNS_RECORD_TYPES = ["A", "AAAA", "MX", "TXT", "CNAME"]


async def _resolve_domain(domain: str, record_type: str, session: aiohttp.ClientSession) -> list[str]:
    """Resolve a single DNS record type for a domain.

    Returns a list of response strings (IP addresses, MX hosts, TXT values, etc.).
    """
    if HAS_DNSPYTHON:
        try:
            resolver = dns.resolver.Resolver()
            resolver.timeout = 5
            resolver.lifetime = 5
            answers = resolver.resolve(domain, record_type)
            return [str(r) for r in answers]
        except Exception:
            return []
    else:
        # Fallback: use nslookup via subprocess (best-effort).
        try:
            proc = await asyncio.create_subprocess_exec(
                "nslookup", "-type=", record_type, domain,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            text = stdout.decode(errors="replace")
            # Parse nslookup output for the records.
            results = []
            for line in text.splitlines():
                line = line.strip()
                if line and not line.startswith("Server:"):
                    results.append(line)
            return results
        except Exception:
            return []


async def _fetch_dns(niche: str, city: str, country: str, session: aiohttp.ClientSession, limit: int = 20) -> list[dict]:
    """Enumerate DNS records for domains hinted at by the niche/city/country.

    In practice, this tries a few candidate domains constructed from the niche
    and location. Returns a list of dicts with keys: domain, record_type,
    value, and source="dns".
    """
    candidates = _domain_candidates(niche, city, country)
    results: list[dict] = []

    async with aiohttp.ClientSession() as http_session:
        for domain in candidates[:10]:  # limit candidate domains
            for record_type in _DNS_RECORD_TYPES[:4]:  # A, AAAA, MX, TXT
                values = await _resolve_domain(domain, record_type, http_session)
                for value in values[:3]:  # limit per record type
                    results.append({
                        "domain": domain,
                        "record_type": record_type,
                        "value": value,
                        "description": f"DNS {record_type} record for {domain}",
                        "category": niche,
                        "source": "dns",
                    })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
    return results


def _domain_candidates(niche: str, city: str, country: str) -> list[str]:
    """Generate candidate domain names from niche + city + country.

    Heuristics: niche-city.{country_ccTLD}, niche-city-business.{country_ccTLD},
    city-niche.{country_ccTLD}, etc.
    """
    city_safe = re.sub(r"[^a-z0-9]+", "-", city.strip().lower())
    country_cc = country.strip().upper()
    candidates = []

    # Niche-city-ccTLD
    candidates.append(f"{city_safe}-{niche.strip().lower().replace(' ', '-')}.{country_cc}" if country_cc else f"{city_safe}-{niche.strip().lower().replace(' ', '-')}")

    # city-niche-ccTLD
    candidates.append(f"{city_safe}-{niche.strip().lower().replace(' ', '-')}.{country_cc}" if country_cc else f"{city_safe}-{niche.strip().lower().replace(' ', '-')}")

    # Just niche-ccTLD (no city)
    candidates.append(f"{niche.strip().lower().replace(' ', '-')}.{country_cc}" if country_cc else f"{niche.strip().lower().replace(' ', '-')}")

    # city-ccTLD (no niche)
    candidates.append(f"{city_safe}.{country_cc}" if country_cc else city_safe)

    return [c for c in candidates if c]


async def search_businesses(niche: str, city: str, country: str, limit: int = 50) -> list[dict]:
    """Enumerate DNS records for domains hinted at by *niche* in *city, country*.

    Returns a list of dicts with keys: domain, record_type, value, description,
    category, and source="dns". May return an empty list if no DNS records are
    found or the resolution service is unavailable.
    """
    async with aiohttp.ClientSession() as session:
        results = await _fetch_dns(niche, city, country, session, limit=limit)
        return results


__all__ = ["search_businesses"]