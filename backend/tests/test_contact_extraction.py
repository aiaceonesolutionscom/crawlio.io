from app.services import contact_extraction as ce


def test_first_valid_email_rejects_asset_filenames():
    """Rendered SPA pages (scraped with a real browser) are full of asset
    references shaped like "name@2x-hash.png" that match the email regex's
    loose shape but are image filenames, not addresses."""
    html = '<img src="map-placeholder@2x-d2d62e1471a04a5643035e8da0142369.png">'
    assert ce.first_valid_email(html) is None


def test_first_valid_email_accepts_real_email():
    html = "Contact us at hello@brightsmile.pk for bookings."
    assert ce.first_valid_email(html) == "hello@brightsmile.pk"


def test_first_valid_email_rejects_blocklisted_domains():
    html = "Reported via sentry.io error@sentry.io tracking pixel"
    assert ce.first_valid_email(html) is None


def test_first_valid_phone_rejects_bare_unformatted_digit_run():
    """A loose digit run with no separators found in free page text is far
    more often a timestamp/order-id/hash than a real displayed phone number."""
    html = "cache-bust=1786024520697"
    assert ce.first_valid_phone(html) is None


def test_first_valid_phone_accepts_formatted_number():
    html = "Call us at +92 21 111 111 001 anytime."
    assert ce.first_valid_phone(html) == "+92 21 111 111 001"


def test_extract_tel_accepts_bare_digits():
    """Unlike first_valid_phone, a tel: href is legitimately allowed to be a
    bare digit run — that's the normal format for tel: links."""
    html = '<a href="tel:+922111100011">Call</a>'
    assert ce.extract_tel(html) == "+922111100011"


def test_extract_tel_rejects_too_short():
    html = '<a href="tel:+92">Call</a>'
    assert ce.extract_tel(html) is None


def test_extract_mailto_accepts_valid_email():
    html = '<a href="mailto:hello@brightsmile.pk?subject=Hi">Email us</a>'
    assert ce.extract_mailto(html) == "hello@brightsmile.pk"


def test_extract_mailto_rejects_invalid_email():
    html = '<a href="mailto:notanemail">Email us</a>'
    assert ce.extract_mailto(html) is None


def test_is_own_website_rejects_map_and_directory_domains():
    assert ce.is_own_website("https://www.waze.com/live-map/directions/x") is False
    assert ce.is_own_website("https://maps.google.com/?q=x") is False
    assert ce.is_own_website("https://www.yelp.com/biz/x") is False


def test_is_own_website_accepts_business_domain():
    assert ce.is_own_website("https://brightsmile.pk") is True
