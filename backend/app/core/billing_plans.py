"""Self-serve billing only covers the Pro plan — Enterprise stays a
sales-quoted, admin-granted plan (see ContactSalesPage on the frontend).

TODO(founder): PRO_PRICE_PKR_PAISA is a rough USD->PKR placeholder (~278/USD)
for the Safepay checkout — confirm the actual PKR price point before going
live; local pricing is often set independently of the USD price, not a pure
FX conversion.
"""
from typing import Literal

BillingCycle = Literal["monthly", "yearly"]

# Stripe amounts are in the smallest currency unit (cents).
PRO_PRICE_USD_CENTS: dict[BillingCycle, int] = {
    "monthly": 7900,
    "yearly": 79000,  # 10x monthly = 2 months free
}

# Safepay amounts are in the smallest currency unit (paisa, PKR * 100).
PRO_PRICE_PKR_PAISA: dict[BillingCycle, int] = {
    "monthly": 22_000_00,
    "yearly": 220_000_00,
}
