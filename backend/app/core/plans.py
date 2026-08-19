PLAN_CAPABILITIES: dict[str, set[str]] = {
    "free": {"leads", "workspaces", "lead_discovery", "export"},
    "pro": {
        "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "export",
        "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
    },
    "enterprise": {
        "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "branding", "sso", "export",
        "lead_discovery", "lead_discovery_enhanced", "ai_lead_filter", "email_agent",
    },
}

# Lead Discovery result cap per search, by plan.
# Hard-capped at 50 for every plan: the scraper is fast enough to fill this
# reliably in a single request, and higher caps only multiply scrape time.
DISCOVERY_LIMITS: dict[str, int] = {
    "free": 50,
    "pro": 50,
    "enterprise": 50,
}

# Max leads that can be *added* (imported) via Lead Discovery per rolling calendar
# day, by plan — independent of the per-search result cap above and of the
# workspace's overall lead_quota.
DAILY_DISCOVERY_IMPORT_LIMITS: dict[str, int] = {
    "free": 50,
    "pro": 100,
    "enterprise": 200,
}

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"leads": 700, "seats": 1},
    "pro": {"leads": 5000, "seats": 10},
    "enterprise": {"leads": 1_000_000_000, "seats": 1_000_000_000},
}
