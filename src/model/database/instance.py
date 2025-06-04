import json
from typing import Optional, List, Dict
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from loguru import logger

Base = declarative_base()


class Wallet(Base):
    __tablename__ = "wallets"
    id = Column(Integer, primary_key=True)
    private_key = Column(String, unique=True)
    proxy = Column(String, nullable=True)
    status = Column(String)  # общий статус кошелька (pending/completed)
    tasks = Column(String)  # JSON строка с задачами


class Database:
    def __init__(self):
        self.engine = create_async_engine(
            "sqlite+aiosqlite:///data/accounts.db",  # Изменен путь и название БД
            echo=False,
        )
        self.session = sessionmaker(
            bind=self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_db(self):
        """Инициализация базы данных"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.success("Database initialized successfully")

    async def clear_database(self):
        """Полная очистка базы данных"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        logger.success("Database cleared successfully")

    async def add_wallet(
        self,
        private_key: str,
        proxy: Optional[str] = None,
        tasks_list: Optional[List[str]] = None,
    ) -> None:
        """
        Добавление нового кошелька

        :param private_key: Приватный ключ кошелька
        :param proxy: Прокси (опционально)
        :param tasks_list: Список названий задач
        """
        # Преобразуем список задач в нужный формат для БД
        tasks = []
        for task in tasks_list or []:
            tasks.append(
                {
                    "name": task,
                    "status": "pending",
                    "index": len(tasks) + 1,  # Добавляем индекс для сохранения порядка
                }
            )

        async with self.session() as session:
            wallet = Wallet(
                private_key=private_key,
                proxy=proxy,
                status="pending",
                tasks=json.dumps(tasks),
            )
            session.add(wallet)
            await session.commit()
            logger.success(f"Added wallet {private_key[:4]}...{private_key[-4:]}")

    async def update_task_status(
        self, private_key: str, task_name: str, new_status: str
    ) -> None:
        """
        Обновление статуса конкретной задачи

        :param private_key: Приватный ключ кошелька
        :param task_name: Название задачи
        :param new_status: Новый статус (pending/completed)
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            if not wallet:
                logger.error(f"Wallet {private_key[:4]}...{private_key[-4:]} not found")
                return

            tasks = json.loads(wallet.tasks)
            for task in tasks:
                if task["name"] == task_name:
                    task["status"] = new_status
                    break

            wallet.tasks = json.dumps(tasks)

            # Проверяем, все ли задачи выполнены
            if all(task["status"] == "completed" for task in tasks):
                wallet.status = "completed"

            await session.commit()
            logger.info(
                f"Updated task {task_name} to {new_status} for wallet {private_key[:4]}...{private_key[-4:]}"
            )

    async def clear_wallet_tasks(self, private_key: str) -> None:
        """
        Очистка всех задач кошелька

        :param private_key: Приватный ключ кошелька
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            if not wallet:
                return

            wallet.tasks = json.dumps([])
            wallet.status = "pending"
            await session.commit()
            logger.info(
                f"Cleared all tasks for wallet {private_key[:4]}...{private_key[-4:]}"
            )

    async def update_wallet_proxy(self, private_key: str, new_proxy: str) -> None:
        """
        Обновление прокси кошелька

        :param private_key: Приватный ключ кошелька
        :param new_proxy: Новый прокси
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            if not wallet:
                return

            wallet.proxy = new_proxy
            await session.commit()
            logger.info(
                f"Updated proxy for wallet {private_key[:4]}...{private_key[-4:]}"
            )

    async def get_wallet_tasks(self, private_key: str) -> List[Dict]:
        """
        Получение всех задач кошелька

        :param private_key: Приватный ключ кошелька
        :return: Список задач с их статусами
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            if not wallet:
                return []
            return json.loads(wallet.tasks)

    async def get_pending_tasks(self, private_key: str) -> List[str]:
        """
        Получение всех незавершенных задач кошелька

        :param private_key: Приватный ключ кошелька
        :return: Список названий незавершенных задач
        """
        tasks = await self.get_wallet_tasks(private_key)
        return [task["name"] for task in tasks if task["status"] == "pending"]

    async def get_completed_tasks(self, private_key: str) -> List[str]:
        """
        Получение всех завершенных задач кошелька

        :param private_key: Приватный ключ кошелька
        :return: Список названий завершенных задач
        """
        tasks = await self.get_wallet_tasks(private_key)
        return [task["name"] for task in tasks if task["status"] == "completed"]

    async def get_uncompleted_wallets(self) -> List[Dict]:
        """
        Получение списка всех кошельков с невыполненными задачами

        :return: Список кошельков с их данными
        """
        async with self.session() as session:
            from sqlalchemy import select

            query = select(Wallet).filter_by(status="pending")
            result = await session.execute(query)
            wallets = result.scalars().all()

            # Преобразуем в список словарей для удобства использования
            return [
                {
                    "private_key": wallet.private_key,
                    "proxy": wallet.proxy,
                    "status": wallet.status,
                    "tasks": json.loads(wallet.tasks),
                }
                for wallet in wallets
            ]

    async def get_wallet_status(self, private_key: str) -> Optional[str]:
        """
        Получение статуса кошелька

        :param private_key: Приватный ключ кошелька
        :return: Статус кошелька или None если кошелёк не найден
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            return wallet.status if wallet else None

    async def _get_wallet(
        self, session: AsyncSession, private_key: str
    ) -> Optional[Wallet]:
        """Внутренний метод для получения кошелька по private_key"""
        from sqlalchemy import select

        result = await session.execute(
            select(Wallet).filter_by(private_key=private_key)
        )
        return result.scalar_one_or_none()

    async def add_tasks_to_wallet(self, private_key: str, new_tasks: List[str]) -> None:
        """
        Добавление новых задач к существующему кошельку

        :param private_key: Приватный ключ кошелька
        :param new_tasks: Список новых задач для добавления
        """
        async with self.session() as session:
            wallet = await self._get_wallet(session, private_key)
            if not wallet:
                return

            current_tasks = json.loads(wallet.tasks)
            current_task_names = {task["name"] for task in current_tasks}

            # Добавляем только новые задачи
            for task in new_tasks:
                if task not in current_task_names:
                    current_tasks.append({"name": task, "status": "pending"})

            wallet.tasks = json.dumps(current_tasks)
            wallet.status = (
                "pending"  # Если добавили новые задачи, статус снова pending
            )
            await session.commit()
            logger.info(
                f"Added new tasks for wallet {private_key[:4]}...{private_key[-4:]}"
            )

    async def get_completed_wallets_count(self) -> int:
        """
        Получение количества кошельков, у которых выполнены все задачи

        :return: Количество завершенных кошельков
        """
        async with self.session() as session:
            from sqlalchemy import select, func

            query = (
                select(func.count()).select_from(Wallet).filter_by(status="completed")
            )
            result = await session.execute(query)
            return result.scalar()

    async def get_total_wallets_count(self) -> int:
        """
        Получение общего количества кошельков в базе

        :return: Общее количество кошельков
        """
        async with self.session() as session:
            from sqlalchemy import select, func

            query = select(func.count()).select_from(Wallet)
            result = await session.execute(query)
            return result.scalar()

    async def get_wallet_completed_tasks(self, private_key: str) -> List[str]:
        """
        Получение списка выполненных задач кошелька

        :param private_key: Приватный ключ кошелька
        :return: Список названий выполненных задач
        """
        tasks = await self.get_wallet_tasks(private_key)
        return [task["name"] for task in tasks if task["status"] == "completed"]

    async def get_wallet_pending_tasks(self, private_key: str) -> List[Dict]:
        """
        Получение списка невыполненных задач кошелька

        :param private_key: Приватный ключ кошелька
        :return: Список задач с их индексами и статусами
        """
        tasks = await self.get_wallet_tasks(private_key)
        return [task for task in tasks if task["status"] == "pending"]

    async def get_completed_wallets(self) -> List[Dict]:
        """
        Получение списка всех кошельков с выполненными задачами

        :return: Список кошельков с их данными
        """
        async with self.session() as session:
            from sqlalchemy import select

            query = select(Wallet).filter_by(status="completed")
            result = await session.execute(query)
            wallets = result.scalars().all()

            return [
                {
                    "private_key": wallet.private_key,
                    "proxy": wallet.proxy,
                    "status": wallet.status,
                    "tasks": json.loads(wallet.tasks),
                }
                for wallet in wallets
            ]

    async def get_wallet_tasks_info(self, private_key: str) -> Dict:
        """
        Получение полной информации о задачах кошелька

        :param private_key: Приватный ключ кошелька
        :return: Словарь с информацией о задачах
        """
        tasks = await self.get_wallet_tasks(private_key)
        completed = [task["name"] for task in tasks if task["status"] == "completed"]
        pending = [task["name"] for task in tasks if task["status"] == "pending"]

        return {
            "total_tasks": len(tasks),
            "completed_tasks": completed,
            "pending_tasks": pending,
            "completed_count": len(completed),
            "pending_count": len(pending),
        }

    async def add_wallets_batch(
        self,
        wallet_data: List[Dict],
    ) -> int:
        """
        Пакетное добавление кошельков в базу данных

        :param wallet_data: Список словарей с данными кошельков
                            (private_key, proxy, tasks_list)
        :return: Количество успешно добавленных кошельков
        """
        added_count = 0
        async with self.session() as session:
            try:
                wallets_to_add = []

                for data in wallet_data:
                    private_key = data["private_key"]
                    proxy = data.get("proxy")
                    tasks_list = data.get("tasks_list", [])

                    # Преобразуем список задач в нужный формат для БД
                    tasks = []
                    for task in tasks_list:
                        tasks.append(
                            {
                                "name": task,
                                "status": "pending",
                                "index": len(tasks)
                                + 1,  # Добавляем индекс для сохранения порядка
                            }
                        )

                    wallet = Wallet(
                        private_key=private_key,
                        proxy=proxy,
                        status="pending",
                        tasks=json.dumps(tasks),
                    )
                    wallets_to_add.append(wallet)

                session.add_all(wallets_to_add)
                await session.commit()
                added_count = len(wallets_to_add)
                logger.success(f"Added {added_count} wallets in batch mode")

            except Exception as e:
                await session.rollback()
                logger.error(f"Error in batch adding wallets: {e}")

        return added_count

    async def update_wallets_tasks_batch(self, wallet_tasks_data: List[Dict]) -> int:
        """
        Пакетное обновление задач для нескольких кошельков

        :param wallet_tasks_data: Список словарей с данными {private_key, tasks_list}
        :return: Количество успешно обновленных кошельков
        """
        updated_count = 0
        async with self.session() as session:
            try:
                from sqlalchemy import select

                for data in wallet_tasks_data:
                    private_key = data["private_key"]
                    new_tasks = data["tasks_list"]

                    # Получаем кошелек
                    result = await session.execute(
                        select(Wallet).filter_by(private_key=private_key)
                    )
                    wallet = result.scalar_one_or_none()

                    if not wallet:
                        logger.warning(
                            f"Wallet {private_key[:4]}...{private_key[-4:]} not found for batch task update"
                        )
                        continue

                    # Подготавливаем новые задачи
                    tasks = []
                    for task in new_tasks:
                        tasks.append(
                            {"name": task, "status": "pending", "index": len(tasks) + 1}
                        )

                    # Обновляем задачи и статус
                    wallet.tasks = json.dumps(tasks)
                    wallet.status = "pending"
                    updated_count += 1

                # Сохраняем все изменения одним коммитом
                await session.commit()
                logger.success(
                    f"Updated tasks for {updated_count} wallets in batch mode"
                )

            except Exception as e:
                await session.rollback()
                logger.error(f"Error in batch updating wallet tasks: {e}")

        return updated_count


# # Создание и инициализация БД
# db = Database()
# await db.init_db()

# # Добавление кошелька с задачами
# await db.add_wallet(
#     private_key="0x123...",
#     proxy="http://proxy1.com",
#     tasks_list=["FAUCET", "OKX_WITHDRAW", "TESTNET_BRIDGE"]
# )

# # Обновление статуса задачи
# await db.update_task_status(
#     private_key="0x123...",
#     task_name="FAUCET",
#     new_status="completed"
# )

# # Получение списка незавершенных задач
# pending_tasks = await db.get_pending_tasks("0x123...")

# # Очистка задач кошелька
# await db.clear_wallet_tasks("0x123...")

# # Добавление новых задач к существующему кошельку
# await db.add_tasks_to_wallet(
#     private_key="0x123...",
#     new_tasks=["NEW_TASK1", "NEW_TASK2"]
# )
