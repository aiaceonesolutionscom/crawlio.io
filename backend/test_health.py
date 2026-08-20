import httpx, json, time

start = time.time()
try:
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            'http://127.0.0.1:8000/api/v1/leads/discover',
            json={'niche': 'restaurants', 'city': 'Lahore', 'country': 'PK', 'limit': 5}
        )
        elapsed = time.time() - start
        print(f'Status: {resp.status_code}')
        print(f'Elapsed: {elapsed:.2f}s')
        if resp.status_code == 200:
            data = resp.json()
            total = data["total"]
            items = len(data["items"])
            print(f'Total: {total}')
            print(f'Items: {items}')
        else:
            print(f'Response: {resp.text[:300]}')
except Exception as e:
    elapsed = time.time() - start
    print(f'Error after {elapsed:.2f}s: {type(e).__name__}: {e}')