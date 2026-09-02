"""Redis-backed JWT blocklist (for logout / token revocation)."""

import redis.asyncio as aioredis

from src.config import Config

token_blocklist = aioredis.from_url(Config.REDIS_URL)

# Blocked token ids expire after this many seconds (matches access-token life).
JTI_EXPIRY = 3600


async def add_jti_to_blocklist(jti: str) -> None:
    await token_blocklist.set(name=jti, value="", ex=JTI_EXPIRY)


async def token_in_blocklist(jti: str) -> bool:
    return (await token_blocklist.get(jti)) is not None
