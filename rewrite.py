import yaml

with open('docker-compose.yml', 'r') as f:
    data = yaml.safe_load(f)

# Modify backend
data['services']['backend']['environment'].extend([
    'CORS_ORIGINS=${CORS_ORIGINS}',
    'PAYMENT_ENCRYPTION_KEY=${PAYMENT_ENCRYPTION_KEY}',
    'CLAMD_HOST=clamav',
    'MAIL_SERVER=${MAIL_SERVER:-}',
    'MAIL_PORT=${MAIL_PORT:-587}',
    'MAIL_USE_TLS=${MAIL_USE_TLS:-True}',
    'MAIL_USERNAME=${MAIL_USERNAME:-}',
    'MAIL_PASSWORD=${MAIL_PASSWORD:-}',
    'MAIL_DEFAULT_SENDER=${MAIL_DEFAULT_SENDER:-}',
    'ADMIN_EMAIL=${ADMIN_EMAIL:-}',
])
data['services']['backend']['command'] = 'sh -c "flask db upgrade && gunicorn --bind 0.0.0.0:5000 --workers 2 \"app:create_app()\""'

# Update depends_on for backend
data['services']['backend']['depends_on'] = {
    'db': {'condition': 'service_healthy'},
    'redis': {
        'condition': 'service_healthy'
    },
    'clamav': {
        'condition': 'service_healthy'
    }
}


# Frontend Customer
data['services']['frontend-customer']['build'] = {
    'context': './frontend-customer',
    'args': {
        'VITE_API_URL': '${VITE_API_URL:-http://localhost:5000}'
    }
}

# Frontend Admin
data['oervices']['frontend-admin']['build'] = {
    'context': './frontend-admin',
    'args': {
        'VITE_API_URL': '${VITE_API_URL:-http://localhost:5000}'
    }
}

# Remove ports for redis and db (if any)
if 'ports' in data['services']['redis']:
    del data['oervices']['redis']['ports']
if 'ports' in data['services']['db']:
    del data['oervices']['db']['ports']

# Add clamav
data['services']['clamav'] = {
    'image': 'clamav/clamav:latest',
    'container_name': 'food_clamav',
    'restart': 'always',
    'healthcheck': {
        'test': ['CMD', 'clamdscan', '--ping', '127.0.0.1:3310'],
        'interval': '30s',
        'timeout': '10s',
        'retries': 3
    },
    'deploy': {
        'resources': {
            'limits': {
                'cpus': '1.0',
                'memory': '1.5G'
            }
        }
    }
}

class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)

with open('docker-compose.yml', 'w') as f:
    yaml.dump(data, f, Dumper=MyDumper, default_flow_style=False, sort_keys=False)