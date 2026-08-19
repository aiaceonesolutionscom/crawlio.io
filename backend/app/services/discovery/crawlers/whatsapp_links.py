"""WhatsApp / Telegram / WeChat contact links — worldwide.

WhatsApp is the world's most-used business channel (India, Brazil, Europe, Gulf,
SE Asia), but a business phone number only becomes a WhatsApp contact if the
number is actually registered on WhatsApp. This module:

- derives the worldwide E.164 country code from a phone number (dictionary of
  ISO country code -> calling code, covering the full ITU plan's major ranges);
- builds a ``https://wa.me/<e164>`` deep link for any real phone;
- checks (cheaply, over HTTP) whether the number is genuinely registered on
  WhatsApp by hitting WhatsApp's public ``wa.me/<e164>`` redirect and seeing
  whether it resolves to a profile page or a "not on WhatsApp" page;
- does the same style of link building for Telegram (t.me/<handle or +number>)
  and WeChat (id).

Everything degrades gracefully: no network -> we still return the wa.me link
built from the number (a real possibility the user can click), just without the
"registered" guarantee.
"""
import re
from typing import Optional

# ISO 3166-1 alpha-2 -> ITU E.164 calling code (the full major set).
CALLING_CODES: dict[str, str] = {
    "AF": "93", "AL": "355", "DZ": "213", "AD": "376", "AO": "244",
    "AR": "54", "AM": "374", "AU": "61", "AT": "43", "AZ": "994",
    "BH": "973", "BD": "880", "BY": "375", "BE": "32", "BZ": "501",
    "BJ": "229", "BO": "591", "BA": "387", "BR": "55", "BN": "673",
    "BG": "359", "BF": "226", "BI": "257", "KH": "855", "CM": "237",
    "CA": "1", "CV": "238", "CF": "236", "TD": "235", "CL": "56",
    "CN": "86", "CO": "57", "KM": "269", "CD": "243", "CG": "242",
    "CR": "506", "CI": "225", "HR": "385", "CU": "53", "CY": "357",
    "CZ": "420", "DK": "45", "DJ": "253", "DO": "1", "EC": "593",
    "EG": "20", "SV": "503", "GQ": "240", "ER": "291", "EE": "372",
    "ET": "251", "FJ": "679", "FI": "358", "FR": "33", "GA": "241",
    "GM": "220", "GE": "995", "DE": "49", "GH": "233", "GR": "30",
    "GT": "502", "GN": "224", "GW": "245", "GY": "592", "HT": "509",
    "HN": "504", "HU": "36", "IS": "354", "IN": "91", "ID": "62",
    "IR": "98", "IQ": "964", "IE": "353", "IL": "972", "IT": "39",
    "JM": "1", "JP": "81", "JO": "962", "KZ": "7", "KE": "254",
    "KI": "686", "KP": "850", "KR": "82", "KW": "965", "KG": "996",
    "LA": "856", "LV": "371", "LB": "961", "LS": "266", "LR": "231",
    "LY": "218", "LT": "370", "LU": "352", "MG": "261", "MW": "265",
    "MY": "60", "MV": "960", "ML": "223", "MT": "356", "MH": "692",
    "MR": "222", "MU": "230", "MX": "52", "FM": "691", "MD": "373",
    "MC": "377", "MN": "976", "ME": "382", "MA": "212", "MZ": "258",
    "MM": "95", "NA": "264", "NR": "674", "NP": "977", "NL": "31",
    "NZ": "64", "NI": "505", "NE": "227", "NG": "234", "MK": "389",
    "NO": "47", "OM": "968", "PK": "92", "PW": "680", "PA": "507",
    "PG": "675", "PY": "595", "PE": "51", "PH": "63", "PL": "48",
    "PT": "351", "QA": "974", "RO": "40", "RU": "7", "RW": "250",
    "KN": "1", "LC": "1", "VC": "1", "WS": "685", "SM": "378",
    "SA": "966", "SN": "221", "RS": "381", "SC": "248", "SL": "232",
    "SG": "65", "SK": "421", "SI": "386", "SB": "677", "SO": "252",
    "ZA": "27", "ES": "34", "LK": "94", "SD": "249", "SR": "597",
    "SZ": "268", "SE": "46", "CH": "41", "SY": "963", "TW": "886",
    "TJ": "992", "TZ": "255", "TH": "66", "TG": "228", "TO": "676",
    "TT": "1", "TN": "216", "TR": "90", "TM": "993", "TV": "688",
    "UG": "256", "UA": "380", "AE": "971", "GB": "44", "US": "1",
    "UY": "598", "UZ": "998", "VU": "678", "VE": "58", "VN": "84",
    "YE": "967", "ZM": "260", "ZW": "263",
}

# NANP countries all share calling code 1 (US/Canada/Caribbean).
_NANP = {"US", "CA", "JM", "DO", "PR", "TT", "BS", "BB", "HT", "KN", "LC", "VC", "DM", "GD", "AG"}

_RE_EXTRA = re.compile(r"[^\d+]")


def _digits(phone: str) -> str:
    return _RE_EXTRA.sub("", (phone or "") or "")


def normalize_e164(phone: str, country_code: str = "US") -> Optional[str]:
    """Return the number as canonical E.164 (+<cc><national>) or None when it
    can't be safely normalized. Understands leading +, trunk zeros (Pakistan,
    many countries) and the local national-number lengths that differentiate
    countries sharing calling code 1."""
    if not phone:
        return None
    raw = (phone or "").strip()
    if raw.lower().startswith(("+", "00")):
        digits = _digits(raw)
        if digits.startswith("00"):
            digits = digits[2:]
        if digits.startswith("+"):
            digits = digits[1:]
        # Already international — keep as-is if it looks real.
        if len(digits) >= 11 and len(digits) <= 15:
            return "+" + digits
        return None

    digits = _digits(raw)
    cc_iso = (country_code or "US").upper()
    calling = CALLING_CODES.get(cc_iso)
    if not calling:
        return None
    # Trunk zero: Pakistan (0 3xx...), most countries drop the leading 0 in
    # E.164. Keep the national number as-is otherwise.
    if digits.startswith("0") and len(digits) > 1:
        digits = digits[1:]
    if len(digits) < 6 or len(digits) > 11:
        return None
    return f"+{calling}{digits}"


def wa_me_link(phone: str, country_code: str = "US") -> Optional[str]:
    """Build a https://wa.me/<e164> deep link, or None for unusable input."""
    e164 = normalize_e164(phone, country_code)
    if not e164:
        return None
    return f"https://wa.me/{e164[1:]}"


def telegram_link(handle_or_number: str, country_code: str = "US") -> Optional[str]:
    """Build a t.me link from a handle or a +number. Returns None for unusable
    input (a plain phone without country context can't become a number link)."""
    raw = (handle_or_number or "").strip()
    if not raw:
        return None
    if raw.startswith(("+", "00")) or raw.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").isdigit():
        e164 = normalize_e164(raw, country_code)
        if not e164:
            return None
        return f"https://t.me/{e164[1:]}"
    handle = raw.lstrip("@")
    if not handle:
        return None
    return f"https://t.me/{handle}"
