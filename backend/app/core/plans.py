PLAN_CAPABILITIES: dict[str, set[str]] = {
    "free": {"leads", "workspaces", "lead_discovery"},
    "pro": {"leads", "workspaces", "automation", "analytics", "team", "whatsapp", "lead_discovery", "lead_discovery_enhanced"},
    "enterprise": {
        "leads", "workspaces", "automation", "analytics", "team", "whatsapp", "branding", "sso", "export",
        "lead_discovery", "lead_discovery_enhanced",
    },
}

# Lead Discovery result cap per search, by plan.
DISCOVERY_LIMITS: dict[str, int] = {
    "free": 50,
    "pro": 100,
    "enterprise": 200,
}

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"leads": 500, "seats": 1},
    "pro": {"leads": 5000, "seats": 10},
    "enterprise": {"leads": 1_000_000_000, "seats": 1_000_000_000},
}
