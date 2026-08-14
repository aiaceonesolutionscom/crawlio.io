"""Open-source lead crawlers (free sources).

This package is the discovery backbone of Crawlio's Lead Center. It contains the
crawlers that produce *real* business leads from free, open sources — Google Maps
(what Apify's flagship "Google Maps Scraper" actor does) and free Pakistan
business directories — plus the validation/merge logic that guarantees only real,
complete contacts are ever shown to a user.

Everything here is intentionally self-contained: it depends only on httpx,
Playwright and dnspython, is configured exclusively through environment
variables, and never requires a paid API key. Failures degrade to empty lists,
never exceptions, so one blocked source can never break a search.
"""
