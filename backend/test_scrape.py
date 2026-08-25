import sys
sys.path.insert(0, 'E:\\crawlio.io\\backend\\app')
from app.services import discovery_service
import inspect
src = inspect.getsource(discovery_service._scrape_city_sources)
print(src)