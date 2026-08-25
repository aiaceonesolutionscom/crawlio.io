import sys
import os

bak_path = 'E:\\\\crawlio.io\\\\backend\\\\app\\\\services\\\\discovery\\\\discovery_service.py.bak'
# Since no backup exists, read the current file
with open('E:\\\\crawlio.io\\\\backend\\\\app\\\\services\\\\discovery\\\\discovery_service.py', 'r', encoding='utf-8') as f:
    original = f.read()

additions = '''

# ──────────────────────────────────────────────────────────────────────
# Fill Loop: Progressive lead generation (replaces oversample/trim)
# ────────────────────────────────────────────────────────────────────

def _fill_loop_plan(niche: str, city: str, country: str, target: int,
                    geo_grid: int = 3, max_grids: int = 5) -> list[dict]:
    """Generate progressive search plan stages to widen the search."""
    plans = []
    if geo_grid >= 1:
        plans.append(("geo_tiling", {"grid": geo_grid}))
    if max_grids >= 2:
        plans.append(("synonyms", {"max_synonyms": 5}))
    if max_grids >= 3:
        plans.append(("adjacent_geo", {"max_adjacent": 3}))
    if max_grids >= 4:
        plans.append(("domain_first", {"max_ct": 20}))
    return plans


def _execute_fill_plan(niche: str, city: str, country: str, target: int,
                       plan: dict, ctx: dict) -> tuple[list[dict], dict]:
    """Execute one stage of the fill plan, return (leads, new_ctx)."""
    leads = []
    new_ctx = dict(ctx)
    stage = plan.get("stage", "geo_tiling")
    
    if stage == "geo_tiling":
        new_ctx["stage"] = "synonyms"
    elif stage == "synonyms":
        new_ctx["stage"] = "adjacent_geo"
    elif stage == "adjacent_geo":
        new_ctx["stage"] = "domain_first"
    elif stage == "domain_first":
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
'''
with open('E:\\\\crawlio.io\\\\backend\\\\app\\\\services\\\\discovery\\\\discovery_service.py', 'a', encoding='utf-8') as f:
    f.write(additions)

print('Fill loop functions appended successfully')
old_len = len(open('E:\\\\crawlio.io\\\\backend\\\\app\\\\services\\\\discovery\\\\discovery_service.py', 'r', encoding='utf-8').read())
new_len = len(open('E:\\\\crawlio.io\\\\backend\\\\app\\\\services\\\\discovery\\\\discovery_service.py', 'r', encoding='utf-8').read())
print(f'File grew from {old_len} to {new_len} bytes')