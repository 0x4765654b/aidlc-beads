"""Retry logic with exponential backoff for agent operations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger("agents.retry")

MAX_RETRIES = 3
BASE_DELAY = 2.0  # seconds

T = TypeVar("T")

TRANSIENT_ERRORS = (TimeoutError, ConnectionError, OSError)


async def with_retry(
    func: Callable[..., Coroutine[Any, Any, T]],
    *args: Any,
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    transient_errors: tuple = TRANSIENT_ERRORS,
    **kwargs: Any,
) -> T:
    """Execute an async function with exponential backoff retry.

    Args:
        func: Async function to call.
        *args: Positional arguments.
        max_retries: Maximum number of attempts.
        base_delay: Base delay in seconds (doubled each retry).
        transient_errors: Exception types that trigger retry.
        **kwargs: Keyword arguments.

    Returns:
        The function's return value.

    Raises:
        The last exception if all retries fail.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except transient_errors as e:
            last_error = e
            if attempt == max_retries - 1:
                logger.error(
                    "All %d retries exhausted for %s: %s",
                    max_retries,
                    func.__name__,
                    e,
                )
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Retry %d/%d for %s after %.1fs: %s",
                attempt + 1,
                max_retries,
                func.__name__,
                delay,
                e,
            )
            await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]  # unreachable but satisfies type checker
