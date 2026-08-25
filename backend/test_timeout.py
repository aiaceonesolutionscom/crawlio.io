import sys
sys.path.insert(0, 'E:\\crawlio.io\\backend\\app')
from app.services import discovery_service
import inspect
src = inspect.getsource(discovery_service)
lines = src.split('\n')
for i, line in enumerate(lines):
    if '_SOURCE_TIMEOUT' in line:
        print(f'{i}: {line}')
    if 'OVERSAMPLE_FACTOR' in line:
        print(f'{i}: {line}')
    if 'PER_SOURCE_FETCH_CAP' in line:
        print(f'{i}: {line}')
    if 'async def _scrape_city_sources' in line:
        print(f'\\n{i}: {line}')