from eth_account import Account
from loguru import logger
import primp
import random
import asyncio

from src.model.projects.mints.morkie import Morkie
from src.model.projects.mints.nerzo import Nerzo
from src.model.projects.domains import ConftApp
from src.model.projects.deploy.zkcodex import ZkCodex
from src.model.projects.other.superboard.instance import SuperBoard
from src.model.projects.mints.rarible.instance import Rarible
from src.model.projects.swaps.rainmakr import Rainmakr
from src.model.projects.deploy.owlto.instance import Owlto
from src.model.projects.other.hopnetwork.instance import HopNetwork
from src.model.projects.deploy.easynode.instance import EasyNode
from src.model.projects.deploy.mintair.instance import Mintair
from src.model.projects.mints.omnihub.instance import OmniHub
from src.model.offchain.cex.instance import CexWithdraw
from src.model.onchain.bridges.crusty_swap.instance import CrustySwap
from src.model.projects.mints.xl_meme.instance import XLMeme
from src.model.projects.other.onchaingm.instance import OnchainGm
from src.model.projects.stakings.teko_finance import TekoFinance
from src.model.projects.swaps.bebop import Bebop
from src.model.projects.swaps.gte import GteSwaps
from src.utils.client import create_client, verify_analytics_data
from src.model.projects.mints.cap_app import CapApp
from src.model.megaeth.faucet import faucet
from src.model.projects.other.gte_faucet.instance import GteFaucet
from src.model.help.stats import WalletStats
from src.model.onchain.web3_custom import Web3Custom
from src.utils.client import create_client
from src.utils.config import Config
from src.model.database.db_manager import Database
from src.utils.telegram_logger import send_telegram_message
from src.utils.reader import read_private_keys


class Start:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config

        self.session: primp.AsyncClient | None = None
        self.megaeth_web3: Web3Custom | None = None

        self.wallet = Account.from_key(self.private_key)
        self.wallet_address = self.wallet.address

    async def initialize(self):
        try:
            try:
                verify_analytics_data()
            except:
                pass
            
            self.session = await create_client(
                self.proxy, self.config.OTHERS.SKIP_SSL_VERIFICATION
            )
            self.megaeth_web3 = await Web3Custom.create(
                self.account_index,
                self.config.RPCS.MEGAETH,
                self.config.OTHERS.USE_PROXY_FOR_RPC,
                self.proxy,
                self.config.OTHERS.SKIP_SSL_VERIFICATION,
            )

            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Error: {e}")
            return False

    async def flow(self):
        try:
            try:
                wallet_stats = WalletStats(self.config, self.megaeth_web3)
                await wallet_stats.get_wallet_stats(
                    self.private_key, self.account_index
                )
            except Exception as e:
                pass

            db = Database()
            try:
                tasks = await db.get_wallet_pending_tasks(self.private_key)
            except Exception as e:
                if "no such table: wallets" in str(e):
                    logger.error(
                        f"{self.account_index} | Database not created or wallets table not found"
                    )
                    if self.config.SETTINGS.SEND_TELEGRAM_LOGS:
                        error_message = (
                            f"⚠️ Database error\n\n"
                            f"Account #{self.account_index}\n"
                            f"Wallet: <code>{self.private_key[:6]}...{self.private_key[-4:]}</code>\n"
                            f"Error: Database not created or wallets table not found"
                        )
                        await send_telegram_message(self.config, error_message)
                    return False
                else:
                    logger.error(
                        f"{self.account_index} | Error getting tasks from database: {e}"
                    )
                    raise

            if not tasks:
                logger.warning(
                    f"{self.account_index} | No pending tasks found in database for this wallet. Exiting..."
                )
                if self.megaeth_web3:
                    await self.megaeth_web3.cleanup()
                return True

            task_plan_msg = [f"{i+1}. {task['name']}" for i, task in enumerate(tasks)]
            logger.info(
                f"{self.account_index} | Task execution plan: {' | '.join(task_plan_msg)}"
            )

            completed_tasks = []
            failed_tasks = []

            # Выполняем задачи
            for task in tasks:
                task_name = task["name"]

                if task_name == "skip":
                    logger.info(f"{self.account_index} | Skipping task: {task_name}")
                    continue

                logger.info(f"{self.account_index} | Executing task: {task_name}")

                success = await self.execute_task(task_name)

                if success:
                    await db.update_task_status(
                        self.private_key, task_name, "completed"
                    )
                    completed_tasks.append(task_name)
                    await self.sleep(task_name)
                else:
                    failed_tasks.append(task_name)
                    if not self.config.FLOW.SKIP_FAILED_TASKS:
                        logger.error(
                            f"{self.account_index} | Failed to complete task {task_name}. Stopping wallet execution."
                        )
                        break
                    else:
                        logger.warning(
                            f"{self.account_index} | Failed to complete task {task_name}. Skipping to next task."
                        )
                        await self.sleep(task_name)

            # Отправляем сообщение в Telegram только в конце всей работы
            if self.config.SETTINGS.SEND_TELEGRAM_LOGS:
                message = (
                    f"🐰 MegaETH Bot Report\n\n"
                    f"💳 Wallet: {self.account_index} | <code>{self.private_key[:6]}...{self.private_key[-4:]}</code>\n\n"
                )

                if completed_tasks:
                    message += f"✅ Completed Tasks:\n"
                    for i, task in enumerate(completed_tasks, 1):
                        message += f"{i}. {task}\n"
                    message += "\n"

                if failed_tasks:
                    message += f"❌ Failed Tasks:\n"
                    for i, task in enumerate(failed_tasks, 1):
                        message += f"{i}. {task}\n"
                    message += "\n"

                total_tasks = len(tasks)
                completed_count = len(completed_tasks)
                message += (
                    f"📊 Statistics:\n"
                    f"Total Tasks: {total_tasks}\n"
                    f"Completed: {completed_count}\n"
                    f"Failed: {len(failed_tasks)}\n"
                    f"Success Rate: {(completed_count/total_tasks)*100:.1f}%\n\n"
                    f"⚙️ Settings:\n"
                    f"Skip Failed: {'Yes' if self.config.FLOW.SKIP_FAILED_TASKS else 'No'}\n"
                )

                await send_telegram_message(self.config, message)

            return len(failed_tasks) == 0

        except Exception as e:
            logger.error(f"{self.account_index} | Error: {e}")

            if self.config.SETTINGS.SEND_TELEGRAM_LOGS:
                error_message = (
                    f"⚠️ Error Report\n\n"
                    f"Account #{self.account_index}\n"
                    f"Wallet: <code>{self.private_key[:6]}...{self.private_key[-4:]}</code>\n"
                    f"Error: {str(e)}"
                )
                await send_telegram_message(self.config, error_message)

            return False
        finally:
            # Cleanup resources
            try:
                if self.megaeth_web3:
                    await self.megaeth_web3.cleanup()
                logger.info(f"{self.account_index} | All sessions closed successfully")
            except Exception as e:
                logger.error(f"{self.account_index} | Error during cleanup: {e}")

    async def execute_task(self, task):
        """Execute a single task"""
        task = task.lower()

        if task == "faucet":
            return await faucet(
                self.session,
                self.account_index,
                self.config,
                self.wallet,
                self.proxy,
            )

        if task == "cap_app":
            cap_app = CapApp(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await cap_app.mint_cUSD()

        if task == "bebop":
            bebop = Bebop(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.proxy,
                self.private_key,
            )
            return await bebop.swaps()
        if task == "gte_swaps":
            gte = GteSwaps(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.proxy,
                self.private_key,
            )
            return await gte.execute_swap()

        if task == "teko_finance":
            teko_finance = TekoFinance(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.proxy,
                self.private_key,
            )
            return await teko_finance.stake()
        
        if task == "teko_faucet":
            teko_finance = TekoFinance(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.proxy,
                self.private_key,
            )
            return await teko_finance.faucet()
        
        if task == "onchain_gm":
            onchain_gm = OnchainGm(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await onchain_gm.GM()

        if task == "crusty_refuel":
            crusty_swap = CrustySwap(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.proxy,
                self.private_key,
            )
            return await crusty_swap.refuel()
        
        if task == "crusty_refuel_from_one_to_all":
            private_keys = read_private_keys("data/private_keys.txt")

            crusty_swap = CrustySwap(
                1,
                self.session,
                self.megaeth_web3,
                self.config,
                Account.from_key(private_keys[0]),
                self.proxy,
                private_keys[0],
            )
            private_keys = private_keys[1:]
            return await crusty_swap.refuel_from_one_to_all(private_keys)
        
        elif task == "cex_withdrawal":
            cex_withdrawal = CexWithdraw(
                self.account_index,
                self.private_key,
                self.config,
            )
            return await cex_withdrawal.withdraw()
        
        if task == "xl_meme":
            xl_meme = XLMeme(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await xl_meme.buy_meme()

        if task == "gte_faucet":
            gte_faucet = GteFaucet(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await gte_faucet.faucet()

        
        if task == "omnihub":
            omnihub = OmniHub(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await omnihub.mint()
        
        if task == "mintair":
            mintair = Mintair(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await mintair.deploy_timer_contract()
        
        if task == "easynode":
            easynode = EasyNode(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await easynode.deploy_contract()
        
        if task == "hopnetwork":
            hopnetwork = HopNetwork(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.private_key,
            )
            return await hopnetwork.waitlist()
        
        if task == "owlto":
            owlto = Owlto(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await owlto.deploy_contract()
        
        if task == "rainmakr":
            rainmakr = Rainmakr(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.private_key,
            )
            return await rainmakr.buy_meme()
        
        if task == "rarible":
            rarible = Rarible(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await rarible.buy_meme()
        
        if task == "superboard":
            superboard = SuperBoard(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,    
                self.wallet,
                self.private_key,
            )
            return await superboard.quests()
        
        if task == "conft_app":
            conft_app = ConftApp(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.private_key,
            )
            return await conft_app.mint()
        
        if task == "zkcodex":
            zkcodex = ZkCodex(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
                self.private_key,
            )
            return await zkcodex.deploy()
        
        if task.startswith("nerzo_"):
            nerzo = Nerzo(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            if task == "nerzo_megaeth":
                return await nerzo.mint_megaeth()
            elif task == "nerzo_fluffle":
                return await nerzo.mint_fluffle()
            
        if task == "morkie_mega":
            morkie = Morkie(
                self.account_index,
                self.session,
                self.megaeth_web3,
                self.config,
                self.wallet,
            )
            return await morkie.mint_mega()
        
        logger.error(f"{self.account_index} | Task {task} not found")
        return False

    async def sleep(self, task_name: str):
        """Делает рандомную паузу между действиями"""
        pause = random.randint(
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
        )
        logger.info(
            f"{self.account_index} | Sleeping {pause} seconds after {task_name}"
        )
        await asyncio.sleep(pause)
