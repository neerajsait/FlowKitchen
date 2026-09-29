import json
import re
from app import create_app

app = create_app()

openapi = {
    "openapi": "3.0.0",
    "info": {
        "title": "FoodPilot API",
        "version": "1.0.0"
    },
    "paths": {}
}

with app.app_context():
    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        
        path = str(rule)
        # Convert Flask path vars to OpenAPI path vars (e.g. <int:id> to {id})
        path = re.sub(r'<[^:]+:([^>]+)>', r'{\1}', path)
        path = re.sub(r'<([^>]+)>', r'{\1}', path)
        
        if path not in openapi["paths"]:
            openapi["paths"][path] = {}
            
        for method in rule.methods:
            if method in ["OPTIONS", "HEAD"]:
                continue
            
            openapi["paths"][path][method.lower()] = {
                "summary": rule.endpoint,
                "responses": {
                    "200": {
                        "description": "OK"
                    }
                }
            }

with open('openapi.json', 'w') as f:
    json.dump(openapi, f, indent=2)

print("openapi.json generated successfully.")
