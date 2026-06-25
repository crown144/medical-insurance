from typing import Any, Dict

from django.conf import settings
from sqlalchemy.engine import URL


def get_source_db_config() -> Dict[str, Any]:
    raw = settings.DATABASES.get('source_medical_db') or {}
    config = {
        'host': raw.get('host') or raw.get('HOST') or '',
        'port': int(raw.get('port') or raw.get('PORT') or 3306),
        'user': raw.get('user') or raw.get('USER') or '',
        'password': raw.get('password') or raw.get('PASSWORD') or '',
        'database': raw.get('database') or raw.get('NAME') or '',
        'charset': raw.get('charset') or 'utf8mb4',
    }
    missing = [key for key in ('host', 'user', 'database') if not config[key]]
    if missing:
        raise ValueError(f"原始医疗库配置不完整，缺少: {', '.join(missing)}")
    return config


def get_source_sqlalchemy_url(drivername: str = 'mysql+mysqlconnector') -> URL:
    config = get_source_db_config()
    return URL.create(
        drivername=drivername,
        username=config['user'],
        password=config['password'],
        host=config['host'],
        port=config['port'],
        database=config['database'],
        query={'charset': config['charset']},
    )
