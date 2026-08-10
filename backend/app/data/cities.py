# Static list of major cities per ISO-3166 country code, used by the Lead
# Discovery city autocomplete. Replaces the previous Nominatim (OpenStreetMap)
# geocoder so the product no longer depends on OSM's free resources at all.
# Coordinates are approximate and only kept for API-shape compatibility — the
# discovery flow is web-based now and never uses them.
#
# search_cities() also passes through a raw typed query when nothing matches
# (see geo_service), so an uncovered city still works as free text.
CITIES: dict[str, list[dict]] = {
    "PK": [
        {"name": "Karachi", "lat": 24.86, "lon": 67.01},
        {"name": "Lahore", "lat": 31.55, "lon": 74.34},
        {"name": "Faisalabad", "lat": 31.45, "lon": 73.13},
        {"name": "Rawalpindi", "lat": 33.56, "lon": 73.03},
        {"name": "Islamabad", "lat": 33.68, "lon": 73.05},
        {"name": "Multan", "lat": 30.16, "lon": 71.52},
        {"name": "Peshawar", "lat": 34.02, "lon": 71.58},
        {"name": "Quetta", "lat": 30.18, "lon": 67.00},
        {"name": "Sialkot", "lat": 32.49, "lon": 74.53},
        {"name": "Gujranwala", "lat": 32.16, "lon": 74.19},
        {"name": "Hyderabad", "lat": 25.40, "lon": 68.37},
        {"name": "Sargodha", "lat": 32.08, "lon": 72.67},
        {"name": "Bahawalpur", "lat": 29.39, "lon": 71.67},
    ],
    "IN": [
        {"name": "Mumbai", "lat": 19.08, "lon": 72.88},
        {"name": "Delhi", "lat": 28.61, "lon": 77.21},
        {"name": "Bengaluru", "lat": 12.97, "lon": 77.59},
        {"name": "Hyderabad", "lat": 17.39, "lon": 78.49},
        {"name": "Chennai", "lat": 13.08, "lon": 80.27},
        {"name": "Kolkata", "lat": 22.57, "lon": 88.36},
        {"name": "Pune", "lat": 18.52, "lon": 73.86},
        {"name": "Ahmedabad", "lat": 23.02, "lon": 72.57},
        {"name": "Jaipur", "lat": 26.91, "lon": 75.79},
        {"name": "Lucknow", "lat": 26.85, "lon": 80.95},
    ],
    "US": [
        {"name": "New York", "lat": 40.71, "lon": -74.01},
        {"name": "Los Angeles", "lat": 34.05, "lon": -118.24},
        {"name": "Chicago", "lat": 41.88, "lon": -87.63},
        {"name": "Houston", "lat": 29.76, "lon": -95.37},
        {"name": "Phoenix", "lat": 33.45, "lon": -112.07},
        {"name": "Philadelphia", "lat": 39.95, "lon": -75.17},
        {"name": "San Antonio", "lat": 29.42, "lon": -98.49},
        {"name": "San Diego", "lat": 32.72, "lon": -117.16},
        {"name": "Dallas", "lat": 32.78, "lon": -96.80},
        {"name": "Seattle", "lat": 47.61, "lon": -122.33},
    ],
    "GB": [
        {"name": "London", "lat": 51.51, "lon": -0.13},
        {"name": "Birmingham", "lat": 52.49, "lon": -1.89},
        {"name": "Manchester", "lat": 53.48, "lon": -2.24},
        {"name": "Leeds", "lat": 53.80, "lon": -1.55},
        {"name": "Glasgow", "lat": 55.86, "lon": -4.25},
        {"name": "Liverpool", "lat": 53.41, "lon": -2.98},
        {"name": "Edinburgh", "lat": 55.95, "lon": -3.19},
    ],
    "AE": [
        {"name": "Dubai", "lat": 25.20, "lon": 55.27},
        {"name": "Abu Dhabi", "lat": 24.45, "lon": 54.38},
        {"name": "Sharjah", "lat": 25.35, "lon": 55.39},
        {"name": "Ajman", "lat": 25.41, "lon": 55.44},
        {"name": "Ras Al Khaimah", "lat": 25.79, "lon": 55.94},
    ],
    "SA": [
        {"name": "Riyadh", "lat": 24.71, "lon": 46.68},
        {"name": "Jeddah", "lat": 21.49, "lon": 39.19},
        {"name": "Mecca", "lat": 21.39, "lon": 39.86},
        {"name": "Medina", "lat": 24.47, "lon": 39.61},
        {"name": "Dammam", "lat": 26.42, "lon": 50.09},
    ],
    "CA": [
        {"name": "Toronto", "lat": 43.65, "lon": -79.38},
        {"name": "Montreal", "lat": 45.50, "lon": -73.57},
        {"name": "Vancouver", "lat": 49.28, "lon": -123.12},
        {"name": "Calgary", "lat": 51.05, "lon": -114.07},
        {"name": "Ottawa", "lat": 45.42, "lon": -75.70},
    ],
    "AU": [
        {"name": "Sydney", "lat": -33.87, "lon": 151.21},
        {"name": "Melbourne", "lat": -37.81, "lon": 144.96},
        {"name": "Brisbane", "lat": -27.47, "lon": 153.03},
        {"name": "Perth", "lat": -31.95, "lon": 115.86},
    ],
    "BD": [
        {"name": "Dhaka", "lat": 23.81, "lon": 90.41},
        {"name": "Chattogram", "lat": 22.36, "lon": 91.78},
        {"name": "Khulna", "lat": 22.85, "lon": 89.54},
        {"name": "Sylhet", "lat": 24.90, "lon": 91.87},
    ],
    "DE": [
        {"name": "Berlin", "lat": 52.52, "lon": 13.40},
        {"name": "Munich", "lat": 48.14, "lon": 11.58},
        {"name": "Hamburg", "lat": 53.55, "lon": 9.99},
        {"name": "Frankfurt", "lat": 50.11, "lon": 8.68},
        {"name": "Cologne", "lat": 50.94, "lon": 6.96},
    ],
    "FR": [
        {"name": "Paris", "lat": 48.86, "lon": 2.35},
        {"name": "Marseille", "lat": 43.30, "lon": 5.37},
        {"name": "Lyon", "lat": 45.76, "lon": 4.84},
        {"name": "Nice", "lat": 43.71, "lon": 7.26},
    ],
    "IT": [
        {"name": "Rome", "lat": 41.90, "lon": 12.50},
        {"name": "Milan", "lat": 45.46, "lon": 9.19},
        {"name": "Naples", "lat": 40.85, "lon": 14.27},
        {"name": "Turin", "lat": 45.07, "lon": 7.69},
    ],
    "ES": [
        {"name": "Madrid", "lat": 40.42, "lon": -3.70},
        {"name": "Barcelona", "lat": 41.39, "lon": 2.17},
        {"name": "Valencia", "lat": 39.47, "lon": -0.38},
        {"name": "Seville", "lat": 37.39, "lon": -5.98},
    ],
    "NL": [
        {"name": "Amsterdam", "lat": 52.37, "lon": 4.90},
        {"name": "Rotterdam", "lat": 51.92, "lon": 4.48},
        {"name": "The Hague", "lat": 52.08, "lon": 4.31},
    ],
    "BE": [
        {"name": "Brussels", "lat": 50.85, "lon": 4.35},
        {"name": "Antwerp", "lat": 51.22, "lon": 4.40},
    ],
    "CH": [
        {"name": "Zurich", "lat": 47.38, "lon": 8.54},
        {"name": "Geneva", "lat": 46.20, "lon": 6.14},
        {"name": "Basel", "lat": 47.56, "lon": 7.59},
    ],
    "SE": [
        {"name": "Stockholm", "lat": 59.33, "lon": 18.07},
        {"name": "Gothenburg", "lat": 57.71, "lon": 11.97},
    ],
    "NO": [
        {"name": "Oslo", "lat": 59.91, "lon": 10.75},
        {"name": "Bergen", "lat": 60.39, "lon": 5.32},
    ],
    "DK": [
        {"name": "Copenhagen", "lat": 55.68, "lon": 12.57},
        {"name": "Aarhus", "lat": 56.16, "lon": 10.21},
    ],
    "IE": [
        {"name": "Dublin", "lat": 53.35, "lon": -6.26},
        {"name": "Cork", "lat": 51.90, "lon": -8.47},
    ],
    "PT": [
        {"name": "Lisbon", "lat": 38.72, "lon": -9.14},
        {"name": "Porto", "lat": 41.16, "lon": -8.61},
    ],
    "GR": [
        {"name": "Athens", "lat": 37.98, "lon": 23.73},
        {"name": "Thessaloniki", "lat": 40.64, "lon": 22.94},
    ],
    "TR": [
        {"name": "Istanbul", "lat": 41.01, "lon": 28.98},
        {"name": "Ankara", "lat": 39.93, "lon": 32.86},
        {"name": "Izmir", "lat": 38.42, "lon": 27.14},
    ],
    "EG": [
        {"name": "Cairo", "lat": 30.04, "lon": 31.24},
        {"name": "Alexandria", "lat": 31.20, "lon": 29.92},
        {"name": "Giza", "lat": 30.01, "lon": 31.21},
    ],
    "NG": [
        {"name": "Lagos", "lat": 6.52, "lon": 3.38},
        {"name": "Abuja", "lat": 9.06, "lon": 7.50},
        {"name": "Port Harcourt", "lat": 4.82, "lon": 7.03},
    ],
    "ZA": [
        {"name": "Johannesburg", "lat": -26.20, "lon": 28.05},
        {"name": "Cape Town", "lat": -33.92, "lon": 18.42},
        {"name": "Durban", "lat": -29.86, "lon": 31.03},
    ],
    "KE": [
        {"name": "Nairobi", "lat": -1.29, "lon": 36.82},
        {"name": "Mombasa", "lat": -4.04, "lon": 39.66},
    ],
    "JP": [
        {"name": "Tokyo", "lat": 35.68, "lon": 139.69},
        {"name": "Osaka", "lat": 34.69, "lon": 135.50},
        {"name": "Kyoto", "lat": 35.01, "lon": 135.77},
        {"name": "Nagoya", "lat": 35.18, "lon": 136.91},
    ],
    "KR": [
        {"name": "Seoul", "lat": 37.57, "lon": 126.98},
        {"name": "Busan", "lat": 35.18, "lon": 129.08},
    ],
    "CN": [
        {"name": "Shanghai", "lat": 31.23, "lon": 121.47},
        {"name": "Beijing", "lat": 39.90, "lon": 116.41},
        {"name": "Shenzhen", "lat": 22.54, "lon": 114.06},
    ],
    "SG": [
        {"name": "Singapore", "lat": 1.35, "lon": 103.82},
    ],
    "MY": [
        {"name": "Kuala Lumpur", "lat": 3.14, "lon": 101.69},
        {"name": "George Town", "lat": 5.41, "lon": 100.33},
    ],
    "ID": [
        {"name": "Jakarta", "lat": -6.21, "lon": 106.85},
        {"name": "Surabaya", "lat": -7.26, "lon": 112.75},
        {"name": "Bandung", "lat": -6.92, "lon": 107.61},
    ],
    "TH": [
        {"name": "Bangkok", "lat": 13.76, "lon": 100.50},
        {"name": "Chiang Mai", "lat": 18.79, "lon": 98.98},
    ],
    "PH": [
        {"name": "Manila", "lat": 14.60, "lon": 120.98},
        {"name": "Cebu City", "lat": 10.32, "lon": 123.89},
    ],
    "VN": [
        {"name": "Ho Chi Minh City", "lat": 10.82, "lon": 106.63},
        {"name": "Hanoi", "lat": 21.03, "lon": 105.85},
    ],
    "MX": [
        {"name": "Mexico City", "lat": 19.43, "lon": -99.13},
        {"name": "Guadalajara", "lat": 20.66, "lon": -103.34},
        {"name": "Monterrey", "lat": 25.68, "lon": -100.32},
    ],
    "BR": [
        {"name": "Sao Paulo", "lat": -23.55, "lon": -46.63},
        {"name": "Rio de Janeiro", "lat": -22.91, "lon": -43.17},
        {"name": "Brasilia", "lat": -15.79, "lon": -47.88},
    ],
    "AR": [
        {"name": "Buenos Aires", "lat": -34.60, "lon": -58.38},
        {"name": "Cordoba", "lat": -31.42, "lon": -64.18},
    ],
    "CL": [
        {"name": "Santiago", "lat": -33.45, "lon": -70.67},
    ],
    "CO": [
        {"name": "Bogota", "lat": 4.71, "lon": -74.07},
        {"name": "Medellin", "lat": 6.25, "lon": -75.56},
    ],
    "PE": [
        {"name": "Lima", "lat": -12.05, "lon": -77.04},
    ],
    "RU": [
        {"name": "Moscow", "lat": 55.76, "lon": 37.62},
        {"name": "Saint Petersburg", "lat": 59.93, "lon": 30.34},
    ],
    "UA": [
        {"name": "Kyiv", "lat": 50.45, "lon": 30.52},
        {"name": "Lviv", "lat": 49.84, "lon": 24.03},
    ],
    "PL": [
        {"name": "Warsaw", "lat": 52.23, "lon": 21.01},
        {"name": "Krakow", "lat": 50.06, "lon": 19.94},
    ],
    "CZ": [
        {"name": "Prague", "lat": 50.08, "lon": 14.44},
        {"name": "Brno", "lat": 49.20, "lon": 16.61},
    ],
    "AT": [
        {"name": "Vienna", "lat": 48.21, "lon": 16.37},
        {"name": "Graz", "lat": 47.07, "lon": 15.44},
    ],
    "HU": [
        {"name": "Budapest", "lat": 47.50, "lon": 19.04},
    ],
    "RO": [
        {"name": "Bucharest", "lat": 44.43, "lon": 26.10},
        {"name": "Cluj-Napoca", "lat": 46.77, "lon": 23.59},
    ],
    "RS": [
        {"name": "Belgrade", "lat": 44.79, "lon": 20.45},
    ],
    "HR": [
        {"name": "Zagreb", "lat": 45.81, "lon": 15.98},
        {"name": "Split", "lat": 43.51, "lon": 16.44},
    ],
    "MA": [
        {"name": "Casablanca", "lat": 33.57, "lon": -7.59},
        {"name": "Rabat", "lat": 34.02, "lon": -6.84},
    ],
    "DZ": [
        {"name": "Algiers", "lat": 36.75, "lon": 3.06},
    ],
    "QA": [
        {"name": "Doha", "lat": 25.29, "lon": 51.53},
    ],
    "KW": [
        {"name": "Kuwait City", "lat": 29.38, "lon": 47.99},
    ],
    "BH": [
        {"name": "Manama", "lat": 26.23, "lon": 50.59},
    ],
    "OM": [
        {"name": "Muscat", "lat": 23.59, "lon": 58.41},
    ],
    "JO": [
        {"name": "Amman", "lat": 31.96, "lon": 35.93},
    ],
    "LB": [
        {"name": "Beirut", "lat": 33.89, "lon": 35.50},
    ],
    "IL": [
        {"name": "Tel Aviv", "lat": 32.09, "lon": 34.78},
        {"name": "Jerusalem", "lat": 31.77, "lon": 35.21},
    ],
    "NP": [
        {"name": "Kathmandu", "lat": 27.72, "lon": 85.32},
    ],
    "LK": [
        {"name": "Colombo", "lat": 6.93, "lon": 79.85},
    ],
}