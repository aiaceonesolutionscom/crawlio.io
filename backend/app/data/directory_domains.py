"""Marketplace/directory/portal domains that must never be accepted as a
single business's own website. These sites aggregate listings for many
businesses; treating one as "the business" produces exactly the bug this file
exists to prevent — a lead named after the portal's own marketing copy, with
the portal's own generic contact info instead of any real business's.

Shared by discovery (deciding whether a search result is a real business
candidate) and enrichment (deciding whether a found "website" is trustworthy)
so both paths stay in sync rather than drifting into two different lists.
"""

# Exact-hostname blocklist (matched on the host or any subdomain of it).
DIRECTORY_DOMAINS: set[str] = {
    # Pakistan-specific marketplaces/portals
    "zameen.com", "olx.com.pk", "olx.com", "pakwheels.com", "daraz.pk",
    "rozee.pk", "opensooq.com", "bayut.com", "propertyfinder.com",
    # Pakistan medical/dental directories (common DuckDuckGo results)
    "marham.pk", "oladoc.com", "dentists10.com", "hamariweb.com",
    "digicard.pk", "ekatlang.com", "findandrate.pk", "drmed.pk",
    "instacare.pk", "bioderma.pk", "mednomics.pk",
    # Medical-appointment / doctor-profile portals (Tavily/DDG return these
    # for almost any named clinic — always a listing, never the business site)
    "whatclinic.com", "tibisahulat.com", "dbohra.com", "healthwire.pk",
    "lybrate.com", "practo.com", "medimaps.com", "healthgrades.com",
    "doctoranywhere.com", "idoktor.pk", "wheree.com", "yellowpages.pk",
    "bizisit.com", "pakdirectory.com.pk", "pk-map.com", "dentin.pk",
    # Foreign maps/geo clones that search engines surface for named businesses
    "yandex.ru", "yandex.com", "mapy.com", "geoview.info", "here.com",
    "placehub.com", "map.google.com", "cnepal.com",
    # News/media domains — a clinic mentioned in an article is not the clinic
    "bbc.com", "bbc.co.uk", "dawn.com", "tribune.com.pk", "thenews.com.pk",
    "dailymail.co.uk", "theguardian.com", "ndtv.com", "timesofindia.com",
    # General classifieds/marketplaces
    "craigslist.org", "mercadolibre.com", "alibaba.com", "aliexpress.com",
    "amazon.com", "ebay.com", "indiamart.com", "tradeindia.com", "sulekha.com",
    # Service-lead marketplaces / B2B review-and-directory sites
    "thumbtack.com", "homeadvisor.com", "angi.com", "bark.com", "clutch.co",
    "g2.com", "capterra.com", "trustpilot.com", "glassdoor.com",
    # Review/directory sites (already used ad hoc in discovery_service — kept here too)
    "yellowpages.com", "yellowpages.com.pk", "yelp.com", "justdial.com", "tripadvisor.com",
    "cybo.com", "hotfrog.com", "bizapedia.com", "zoominfo.com",
}

# Generic substring fragments — a catch-all for portals not individually
# listed above. Matched against the lowercased hostname only (never the full
# URL/path), so this can't accidentally reject a real business whose page
# happens to mention one of these words in its content.
DIRECTORY_MARKERS: tuple[str, ...] = (
    "directory", "marketplace", "classifieds", "listing",
    "darpak", "foodiespakistan",
)
