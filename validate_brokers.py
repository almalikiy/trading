from fastapi.testclient import TestClient
from trading_bot.app.main import app

client = TestClient(app)
resp1 = client.get('/brokers')
resp2 = client.get('/brokers/default')
print('BROKERS_STATUS', resp1.status_code)
print('BROKERS_BODY', resp1.json())
print('DEFAULT_STATUS', resp2.status_code)
print('DEFAULT_BODY', resp2.json())
