from fastapi.testclient import TestClient
import sys, os
sys.path.append(os.path.abspath("apps/api"))
from main import app

def test_health():
    client = TestClient(app)
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'healthy'
