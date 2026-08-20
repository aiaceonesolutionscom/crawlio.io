from fastapi.testclient import TestClient
from app.main import app

# List all dependency overrides
print("Dependency overrides:", app.dependency_overrides)

# Try to figure out the auth dependency name
import importlib
mod = importlib.import_module("app.core.dependencies")
print("Dependencies module:", dir(mod))