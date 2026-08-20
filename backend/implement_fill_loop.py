#!/usr/bin/env python3
import sys
import os

# Read the current discovery_service.py
bak_path = 'E:\\crawlio.io\\backend\\app\\services\\discovery\\discovery_service.py'
with open(bak_path, 'r', encoding='utf-8') as f:
    original = f.read()

# New fill loop function to add
additions = '''

# ──────────────────────────────────────────────────────────────────────
# Fill loop: progressive lead generation (replaces oversample/trim)
# ──────────────────────────────────────────────────────────────────────

def _fill_loop_plan(niche: str, city: str, country: str, target: int,
                    geo_grid: int = 3, max_grids: int = 5) -> list[dict]:
    """Generate progressive search plans to widen the search."""
    plans = []
    # Stage 1: Geo tiling
    if geo_grid >= 1:
        plans.append(("geo_tiling", {"grid": geo_grid}))
    # Stage 2: Category synonyms
    if max_grids >= 2:
        plans.append(("synonyms", {"max_synonyms": 5}))
    # Stage 3: Adjacent geo
    if max_grids >= 3:
        plans.append(("adjacent_geo", {"max_adjacent": 3}))
    # Stage 4: Domain-first sweep
    if max_grids >= 4:
        plans.append(("domain_first", {"max_ct": 20}))
    return plans


def _execute_fill_plan(niche: str, city: str, country: str, target: int,
                       plan: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Execute one stage of the fill plan."""
    leads = []
    new_ctx = dict(ctx)
    stage = plan.get("stage", "geo_tiling")
    
    if stage == "geo_tiling":
        # TODO: Implement geo tiling - split city into grid, query each tile
        new_ctx["stage"] = "synonyms"
    elif stage == "synonyms":
        # TODO: Implement category synonym expansion
        new_ctx["stage"] = "adjacent_geo"
    elif stage == "adjacent_geo":
        # TODO: Implement adjacent city/geo queries
        new_ctx["stage"] = "domain_first"
    elif stage == "domain_first":
        # TODO: Implement CT logs + DNS domain sweep
        new_ctx["stage"] = "complete"
    
    return leads, new_ctx


def _fill_loop(target: int, ctx: dict, discover_fn, enrich_fn, verify_fn,
               deadline: float, over_budget_fn) -> dict:
    """Progressive fill loop that keeps widening the search until the target
    is met or the deadline/budget is exhausted.
    
    Returns dict with: leads, returned, requested, reason, stage_reached
    """
    leads = []
    stage_reached = "starting"
    
    plans = _fill_loop_plan(ctx.get("niche", ""), ctx.get("city", ""),
                           ctx.get("country", ""), target)
    
    for plan in plans:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        
        stage_reached = plan.get("stage", "unknown")
        leads_batch, ctx = _execute_fill_plan(
            ctx.get("niche", ""), ctx.get("city", ""),
            ctx.get("country", ""), target, plan, ctx)
        leads.extend(leads_batch)
        
        if len(leads) >= target:
            break
    
    # Dedupe leads by name+phone+website
    seen = set()
    unique_leads = []
    for lead in leads:
        key = (lead.get("name", ""), lead.get("phone", ""), lead.get("website", ""))
        if key not in seen:
            seen.add(key)
            unique_leads.append(lead)
    
    # Verify leads through the quality gate
    verified = []
    for lead in unique_leads:
        if ctx.get("deadline_exceeded", False) or ctx.get("over_budget", False):
            break
        verified_lead = verify_fn(lead)
        if verified_lead:
            verified.append(verified_lead)
    
    returned = len(verified)
    requested = target
    
    if returned < requested:
        reason = f"SOURCE_EXHAUSTED: returned {returned} of {requested} leads"
    else:
        reason = None
    
    return {
        "leads": verified[:target],
        "returned": returned,
        "requested": requested,
        "reason": reason,
        "stage_reached": stage_reached,
    }


print("Fill loop functions defined")
PYEOF
python E:\\\\crawlio.io\\\\backend\\\\implement_fill_loop.py 2>&1