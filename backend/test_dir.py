import sys
sys.path.insert(0, 'E:\\crawlio.io\\backend\\app')
from app.services.crawlers.directory_scraper import _yellowpage_pk, _hotfrog
import asyncio

async def test():
    # Test YellowPage.pk
    records = await _yellowpage_pk('restaurants', 'Lahore', 'Pakistan', 50)
    print(f'YellowPage.pk: {len(records)} records')
    for r in records[:5]:
        print(f'  {r}')
    
    # Test Hotfrog
    records2 = await _hotfrog('restaurants', 'Chicago', 'United States', 50)
    print(f'Hotfrog: {len(records2)} records')
    for r in records2[:5]:
        print(f'  {r}')

asyncio.run(test())