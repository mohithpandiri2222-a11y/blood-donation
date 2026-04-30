import urllib.request
import json

try:
    with urllib.request.urlopen("http://127.0.0.1:5000/api/inventory") as response:
        data = json.loads(response.read().decode())
        print(f"API returned {len(data)} items.")
        for item in data:
            print(f"  {item['bank_name']} - {item['blood_group']}: {item['units']} units")
except Exception as e:
    print(f"Error: {e}")
