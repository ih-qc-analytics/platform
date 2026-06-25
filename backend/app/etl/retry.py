from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


async def async_retry(
    coro_fn,
    *,
    attempts: int = 3,
    backoff_base: float = 2.0,
    exceptions: tuple = (Exception,),
):
    """
    Call coro_fn() up to `attempts` times, sleeping backoff_base**attempt seconds between tries.
    Raises the last exception if all attempts fail.
    """
    last_exc = None
    for attempt in range(attempts):
        try:
            return await coro_fn()
        except exceptions as exc:
            last_exc = exc
            if attempt < attempts - 1:
                delay = backoff_base**attempt  # 1s, 2s, 4s
                logger.warning(
                    "Attempt %d/%d failed (%s), retrying in %.0fs",
                    attempt + 1,
                    attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
    raise last_exc
