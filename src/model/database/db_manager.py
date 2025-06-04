import asyncio
import json
import random
from typing import List
from tabulate import tabulate
from loguru import logger

from src.model.database.instance import Database
from src.utils.config import get_config
from src.utils.reader import read_private_keys
from src.utils.proxy_parser import Proxy  # Добавляем импорт


async def show_database_menu():
    while True:
        print("\nDatabase Management Options:\n")
        print("[1] 🗑  Create/Reset Database")
        print("[2] ➕ Generate New Tasks for Completed Wallets")
        print("[3] 📊 Show Database Contents")
        print("[4] 🔄 Regenerate Tasks for All Wallets")
        print("[5] 📝 Add Wallets to Database")
        print("[6] 👋 Exit")
        print()

        try:
            choice = input("Enter option (1-6): ").strip()

            if choice == "1":
                await reset_database()
            elif choice == "2":
                await regenerate_tasks_for_completed()
            elif choice == "3":
                await show_database_contents()
            elif choice == "4":
                await regenerate_tasks_for_all()
            elif choice == "5":
                await add_new_wallets()
            elif choice == "6":
                print("\nExiting database management...")
                break
            else:
                logger.error("Invalid choice. Please enter a number between 1 and 6.")

        except Exception as e:
            logger.error(f"Error in database management: {e}")
            await asyncio.sleep(1)


async def reset_database():
    """Создание новой или сброс существующей базы данных"""
    print("\n⚠️ WARNING: This will delete all existing data.")
    print("[1] Yes")
    print("[2] No")

    confirmation = input("\nEnter your choice (1-2): ").strip()

    if confirmation != "1":
        logger.info("Database reset cancelled")
        return

    try:
        db = Database()
        await db.clear_database()
        await db.init_db()

        # Генерируем задачи для новой базы данных
        config = get_config()
        private_keys = read_private_keys("data/private_keys.txt")

        # Читаем прокси
        try:
            proxy_objects = Proxy.from_file("data/proxies.txt")
            proxies = [proxy.get_default_format() for proxy in proxy_objects]
            if len(proxies) == 0:
                logger.error("No proxies found in data/proxies.txt")
                return
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            return

        # Подготавливаем данные для пакетного добавления кошельков
        wallet_data = []
        for i, private_key in enumerate(private_keys):
            proxy = proxies[i % len(proxies)]

            # Генерируем новый список задач для каждого кошелька
            tasks = generate_tasks_from_config(config)

            if not tasks:
                logger.error(
                    f"No tasks generated for wallet {private_key[:4]}...{private_key[-4:]}"
                )
                continue

            wallet_data.append(
                {"private_key": private_key, "proxy": proxy, "tasks_list": tasks}
            )

        # Добавляем кошельки пакетно
        if wallet_data:
            added_count = await db.add_wallets_batch(wallet_data)
            logger.success(
                f"Database has been reset and initialized with {added_count} wallets in batch mode!"
            )
        else:
            logger.warning("No wallet data prepared for adding to database")

    except Exception as e:
        logger.error(f"Error resetting database: {e}")


def generate_tasks_from_config(config) -> List[str]:
    """Генерация списка задач из конфига в том же формате, что и в start.py"""
    planned_tasks = []

    # Получаем список задач из конфига
    for task_name in config.FLOW.TASKS:
        # Импортируем tasks.py для получения конкретного списка задач
        import tasks

        # Получаем список подзадач для текущей задачи
        task_list = getattr(tasks, task_name)

        # Обрабатываем каждую подзадачу
        for task_item in task_list:
            if isinstance(task_item, list):
                # Для задач в [], выбираем случайную
                selected_task = random.choice(task_item)
                planned_tasks.append(selected_task)
            elif isinstance(task_item, tuple):
                # Для задач в (), перемешиваем все
                shuffled_tasks = list(task_item)
                random.shuffle(shuffled_tasks)
                # Добавляем все задачи из кортежа
                planned_tasks.extend(shuffled_tasks)
            else:
                # Обычная задача
                planned_tasks.append(task_item)

    logger.info(f"Generated tasks sequence: {planned_tasks}")
    return planned_tasks


async def regenerate_tasks_for_completed():
    """Генерация новых задач для завершенных кошельков"""
    try:
        db = Database()
        config = get_config()

        # Получаем список завершенных кошельков
        completed_wallets = await db.get_completed_wallets()

        if not completed_wallets:
            logger.info("No completed wallets found")
            return

        print("\n[1] Yes")
        print("[2] No")
        confirmation = input(
            "\nThis will replace all tasks for completed wallets. Continue? (1-2): "
        ).strip()

        if confirmation != "1":
            logger.info("Task regeneration cancelled")
            return

        # Подготавливаем данные для пакетного обновления
        wallet_tasks_data = []

        # Для каждого завершенного кошелька генерируем новые задачи
        for wallet in completed_wallets:
            # Генерируем новый список задач
            new_tasks = generate_tasks_from_config(config)

            wallet_tasks_data.append(
                {"private_key": wallet["private_key"], "tasks_list": new_tasks}
            )

        # Обновляем задачи для всех кошельков пакетно
        updated_count = await db.update_wallets_tasks_batch(wallet_tasks_data)
        logger.success(
            f"Generated new tasks for {updated_count} completed wallets in batch mode"
        )

    except Exception as e:
        logger.error(f"Error regenerating tasks: {e}")


async def regenerate_tasks_for_all():
    """Генерация новых задач для всех кошельков"""
    try:
        db = Database()
        config = get_config()

        # Получаем все кошельки
        completed_wallets = await db.get_completed_wallets()
        uncompleted_wallets = await db.get_uncompleted_wallets()
        all_wallets = completed_wallets + uncompleted_wallets

        if not all_wallets:
            logger.info("No wallets found in database")
            return

        print("\n[1] Yes")
        print("[2] No")
        confirmation = input(
            "\nThis will replace all tasks for ALL wallets. Continue? (1-2): "
        ).strip()

        if confirmation != "1":
            logger.info("Task regeneration cancelled")
            return

        # Подготавливаем данные для пакетного обновления
        wallet_tasks_data = []

        # Для каждого кошелька генерируем новые задачи
        for wallet in all_wallets:
            # Генерируем новый список задач
            new_tasks = generate_tasks_from_config(config)

            wallet_tasks_data.append(
                {"private_key": wallet["private_key"], "tasks_list": new_tasks}
            )

        # Обновляем задачи для всех кошельков пакетно
        updated_count = await db.update_wallets_tasks_batch(wallet_tasks_data)
        logger.success(
            f"Generated new tasks for all {updated_count} wallets in batch mode"
        )

    except Exception as e:
        logger.error(f"Error regenerating tasks for all wallets: {e}")


async def show_database_contents():
    """Отображение содержимого базы данных в табличном формате"""
    try:
        db = Database()

        # Получаем все кошельки
        completed_wallets = await db.get_completed_wallets()
        uncompleted_wallets = await db.get_uncompleted_wallets()
        all_wallets = completed_wallets + uncompleted_wallets

        if not all_wallets:
            logger.info("Database is empty")
            return

        # Подготавливаем данные для таблицы
        table_data = []
        for wallet in all_wallets:
            tasks = (
                json.loads(wallet["tasks"])
                if isinstance(wallet["tasks"], str)
                else wallet["tasks"]
            )

            # Форматируем список задач
            completed_tasks = [
                task["name"] for task in tasks if task["status"] == "completed"
            ]
            pending_tasks = [
                task["name"] for task in tasks if task["status"] == "pending"
            ]

            # Сокращаем private key для отображения
            short_key = f"{wallet['private_key'][:6]}...{wallet['private_key'][-4:]}"

            # Форматируем прокси для отображения
            proxy = wallet["proxy"]
            if proxy and len(proxy) > 20:
                proxy = f"{proxy[:17]}..."

            table_data.append(
                [
                    short_key,
                    proxy or "No proxy",
                    wallet["status"],
                    f"{len(completed_tasks)}/{len(tasks)}",
                    ", ".join(completed_tasks) or "None",
                    ", ".join(pending_tasks) or "None",
                ]
            )

        # Создаем таблицу
        headers = [
            "Wallet",
            "Proxy",
            "Status",
            "Progress",
            "Completed Tasks",
            "Pending Tasks",
        ]
        table = tabulate(table_data, headers=headers, tablefmt="grid", stralign="left")

        # Выводим статистику
        total_wallets = len(all_wallets)
        completed_count = len(completed_wallets)
        print(f"\nDatabase Statistics:")
        print(f"Total Wallets: {total_wallets}")
        print(f"Completed Wallets: {completed_count}")
        print(f"Pending Wallets: {total_wallets - completed_count}")

        # Выводим таблицу
        print("\nDatabase Contents:")
        print(table)

    except Exception as e:
        logger.error(f"Error showing database contents: {e}")


async def add_new_wallets():
    """Добавление новых кошельков из файла в базу данных"""
    try:
        db = Database()
        config = get_config()

        # Читаем все приватные ключи из файла
        private_keys = read_private_keys("data/private_keys.txt")

        # Читаем прокси
        try:
            proxy_objects = Proxy.from_file("data/proxies.txt")
            proxies = [proxy.get_default_format() for proxy in proxy_objects]
            if len(proxies) == 0:
                logger.error("No proxies found in data/proxies.txt")
                return
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")
            return

        # Получаем существующие кошельки из базы
        completed_wallets = await db.get_completed_wallets()
        uncompleted_wallets = await db.get_uncompleted_wallets()
        existing_wallets = {
            w["private_key"] for w in (completed_wallets + uncompleted_wallets)
        }

        # Находим новые кошельки
        new_wallets = [pk for pk in private_keys if pk not in existing_wallets]

        if not new_wallets:
            logger.info("No new wallets found to add")
            return

        print(f"\nFound {len(new_wallets)} new wallets to add to database")
        print("\n[1] Yes")
        print("[2] No")
        confirmation = input("\nDo you want to add these wallets? (1-2): ").strip()

        if confirmation != "1":
            logger.info("Adding new wallets cancelled")
            return

        # Подготавливаем данные для пакетного добавления
        wallet_data = []
        for i, private_key in enumerate(new_wallets):
            proxy = proxies[i % len(proxies)]
            tasks = generate_tasks_from_config(config)

            if not tasks:
                logger.error(
                    f"No tasks generated for wallet {private_key[:4]}...{private_key[-4:]}"
                )
                continue

            wallet_data.append(
                {"private_key": private_key, "proxy": proxy, "tasks_list": tasks}
            )

        # Добавляем кошельки пакетно
        if wallet_data:
            added_count = await db.add_wallets_batch(wallet_data)
            logger.success(
                f"Successfully added {added_count} new wallets to database in batch mode!"
            )
        else:
            logger.warning("No wallet data prepared for adding to database")

    except Exception as e:
        logger.error(f"Error adding new wallets: {e}")
