PLAN_CAPABILITIES: dict[str, set[str]] = {
    "free": {"leads", "workspaces"},
    "pro": {"leads", "workspaces", "automation", "analytics", "team", "whatsapp"},
    "enterprise": {"leads", "workspaces", "automation", "analytics", "team", "whatsapp", "branding", "sso"},
}

PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"leads": 500, "seats": 1},
    "pro": {"leads": 5000, "seats": 10},
    "enterprise": {"leads": 1_000_000_000, "seats": 1_000_000_000},
}
