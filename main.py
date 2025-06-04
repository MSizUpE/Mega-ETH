from loguru import logger
import urllib3
import sys
import asyncio
import platform
import logging

from process import start
from src.utils.output import show_logo, show_dev_info
from src.utils.check_github_version import check_version
from src.utils.client import verify_analytics_data

try:
    verify_analytics_data()
except:
    pass

if platform.system() == "Windows":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main():
    show_logo()
    show_dev_info()
    
    configuration()
    await start()


log_format = (
    "<light-blue>[</light-blue><yellow>{time:HH:mm:ss}</yellow><light-blue>]</light-blue> | "
    "<level>{level: <8}</level> | "
    "<cyan>{file}:{line}</cyan> | "
    "<level>{message}</level>"
)


def configuration():
    urllib3.disable_warnings()
    logger.remove()

    # Disable primp and web3 logging
    logging.getLogger("primp").setLevel(logging.WARNING)
    logging.getLogger("web3").setLevel(logging.WARNING)

    logger.add(
        sys.stdout,
        colorize=True,
        format=log_format,
    )
    logger.add(
        "logs/app.log",
        rotation="10 MB",
        retention="1 month",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}",
        level="INFO",
    )

if __name__ == "__main__":
    asyncio.run(main())
