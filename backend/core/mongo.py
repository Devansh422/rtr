"""MongoDB handle.

Mongo keeps what it is genuinely good at after Phase 0: loosely structured CMS
content (blogs, news, FAQ, campaigns, media metadata) where schema flexibility
beats relational integrity, plus the existing submission collections. Anything
that needs joins, aggregation across entities or referential integrity lives in
Postgres -- see core/models.py.
"""

from motor.motor_asyncio import AsyncIOMotorClient

from backend.core import config

client = AsyncIOMotorClient(config.MONGO_URL)
db = client[config.DB_NAME]


def content_coll(ctype: str):
    """Collection backing one CMS content type, e.g. content_blogs."""
    return db[f"content_{ctype}"]


def close() -> None:
    client.close()
