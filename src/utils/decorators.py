from functools import wraps
import asyncio
from typing import TypeVar, Callable, Any, Optional
from loguru import logger
from src.utils.config import get_config

T = TypeVar("T")


# @retry_async(attempts=3, default_value=False)
# async def deploy_contract(self):
#     try:
#         # ваш код деплоя
#         return True
#     except Exception as e:
#         # ваша обработка ошибки с паузой
#         await asyncio.sleep(your_pause)
#         raise  # это вернет управление декоратору для следующей попытки
#
# @retry_async(default_value=False)
# async def some_function():
#     ...

def retry_async(
    attempts: int = None,  # Make attempts optional
    delay: float = 1.0,
    backoff: float = 2.0,
    default_value: Any = None,
):
    """
    Async retry decorator with exponential backoff.
    If attempts is not provided, uses SETTINGS.ATTEMPTS from config.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get attempts from config if not provided
            retry_attempts = attempts if attempts is not None else get_config().SETTINGS.ATTEMPTS
            current_delay = delay

            for attempt in range(retry_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    if attempt < retry_attempts - 1:  # Don't sleep on the last attempt
                        logger.warning(
                            f"Attempt {attempt + 1}/{retry_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay:.1f} seconds..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {retry_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
                        raise e  # Re-raise the last exception

            return default_value

        return wrapper

    return decorator
