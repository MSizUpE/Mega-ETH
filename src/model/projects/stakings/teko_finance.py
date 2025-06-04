import asyncio
import random
import hashlib
import time
import os

from eth_account.messages import encode_typed_data
from eth_account import Account
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
from web3 import Web3
from curl_cffi.requests import AsyncSession

from src.utils.decorators import retry_async
from src.utils.config import Config
from src.utils.constants import EXPLORER_URL_MEGAETH

CHAIN_ID = 6342  # From constants.py comment


class TekoFinance:
    def __init__(
        self,
        account_index: int,
        session: primp.AsyncClient,
        web3: Web3Custom,
        config: Config,
        wallet: Account,
        proxy: str,
        private_key: str,
    ):
        self.account_index = account_index
        self.session = session
        self.web3 = web3
        self.config = config
        self.wallet = wallet
        self.proxy = proxy
        self.private_key = private_key

    async def faucet(self):
        try:
            payloads = [
                {
                    "token": "tkETH",
                    "payload": f"0x40c10f19000000000000000000000000{self.wallet.address.lower()[2:]}0000000000000000000000000000000000000000000000000de0b6b3a7640000",
                    "contract": Web3.to_checksum_address(
                        "0x176735870dc6C22B4EBFBf519DE2ce758de78d94"
                    ),
                },
                {
                    "token": "tkUSDC",
                    "payload": f"0x40c10f19000000000000000000000000{self.wallet.address.lower()[2:]}0000000000000000000000000000000000000000000000000000000077359400",
                    "contract": Web3.to_checksum_address(
                        "0xFaf334e157175Ff676911AdcF0964D7f54F2C424"
                    ),
                },
                {
                    "token": "tkWBTC",
                    "payload": f"0x40c10f19000000000000000000000000{self.wallet.address.lower()[2:]}00000000000000000000000000000000000000000000000000000000001e8480",
                    "contract": Web3.to_checksum_address(
                        "0xF82ff0799448630eB56Ce747Db840a2E02Cde4D8"
                    ),
                },
                {
                    "token": "cUSD",
                    "payload": f"0x40c10f19000000000000000000000000{self.wallet.address.lower()[2:]}00000000000000000000000000000000000000000000003635c9adc5dea00000",
                    "contract": Web3.to_checksum_address(
                        "0xE9b6e75C243B6100ffcb1c66e8f78F96FeeA727F"
                    ),
                },
            ]

            random.shuffle(payloads)

            for payload in payloads:
                await self._request_faucet_token(
                    payload["token"], payload["payload"], payload["contract"]
                )
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                )
                logger.info(
                    f"{self.account_index} | Waiting {random_pause} seconds before next faucet request..."
                )
                await asyncio.sleep(random_pause)


            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Faucet failed: {e}")
            return False

    async def stake(self):
        try:
            logger.info(f"{self.account_index} | Staking in Teko Finance...")

            # Token address for tkUSDC
            token_address = Web3.to_checksum_address(
                "0xFaf334e157175Ff676911AdcF0964D7f54F2C424"
            )

            # Get token balance for tkUSDC
            token_contract = self.web3.web3.eth.contract(
                address=token_address,
                abi=[
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function",
                    }
                ],
            )

            token_balance = await token_contract.functions.balanceOf(
                self.wallet.address
            ).call()

            if token_balance == 0:
                logger.warning(f"{self.account_index} | No tkUSDC balance to stake")
                return False

            # Форматируем баланс для отображения
            formatted_balance = token_balance / 10**6
            logger.info(
                f"{self.account_index} | Current tkUSDC balance: {formatted_balance:.6f} USDC"
            )

            # Approve tokens for spending
            approve_data = "0x095ea7b300000000000000000000000013c051431753fce53eaec02af64a38a273e198d0ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
            await self._approve(token_address, "tkUSDC", approve_data)

            # Calculate stake amount based on config percentage
            min_percent, max_percent = (
                self.config.STAKINGS.TEKO_FINANCE.BALANCE_PERCENTAGE_TO_STAKE
            )
            stake_percentage = random.uniform(min_percent, max_percent)
            amount_to_stake = int(token_balance * stake_percentage / 100)

            # Форматируем сумму для стейкинга
            formatted_amount = amount_to_stake / 10**6
            logger.info(
                f"{self.account_index} | Will stake {stake_percentage:.2f}% of tkUSDC: {formatted_amount:.6f} USDC"
            )

            # Make deposit
            await self._deposit_tkUSDC(amount_to_stake)

            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Staking failed: {e}")
            return False

    @retry_async(default_value=False)
    async def _deposit(self, token_name: str, token_address: str, approve_data: str):
        try:
            logger.info(f"{self.account_index} | Depositing {token_name}...")

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Deposit failed: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _request_faucet_token(self, token_name: str, payload: str, contract: str):
        try:
            logger.info(
                f"{self.account_index} | Requesting Teko Finance faucet token: {token_name}"
            )

            # Prepare basic transaction
            tx = {
                "from": self.wallet.address,
                "to": contract,
                "data": payload,
                "value": 0,
            }

            # Estimate gas
            try:
                gas_limit = await self.web3.estimate_gas(tx)
                tx["gas"] = gas_limit
            except Exception as e:
                raise e

            # Execute transaction using web3_custom methods
            tx_hex = await self.web3.execute_transaction(
                tx_data=tx,
                wallet=self.wallet,
                chain_id=CHAIN_ID,
                explorer_url=EXPLORER_URL_MEGAETH,
            )

            if tx_hex:
                logger.success(
                    f"{self.account_index} | Teko Finance {token_name} minted successfully!"
                )
                return True
            else:
                logger.error(f"{self.account_index} | Transaction failed.")
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error requesting Teko Finance faucet token: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _approve(self, token_address: str, token_name: str, approve_data: str):
        try:
            logger.info(f"{self.account_index} | Approving {token_name}...")

            # Get gas parameters
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Prepare transaction parameters
            tx = {
                "from": self.wallet.address,
                "to": token_address,
                "data": approve_data,
                "value": 0,  # No ETH value sent
                "nonce": await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                ),
                "chainId": CHAIN_ID,
                **gas_params,
            }

            # Estimate gas
            try:
                gas_limit = await self.web3.estimate_gas(tx)
                tx["gas"] = gas_limit
            except Exception as e:
                raise e

            # Set transaction type based on gas params
            if "maxFeePerGas" in gas_params:
                tx["type"] = 2

            # Sign transaction
            signed_tx = self.web3.web3.eth.account.sign_transaction(tx, self.wallet.key)

            # Send transaction
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
            tx_hex = tx_hash.hex()

            # Wait for transaction receipt
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | {token_name} approved for spending successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | {token_name} approval transaction failed."
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error approving {token_name} for Teko Finance: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _deposit_tkUSDC(self, amount):
        try:
            # Форматируем сумму для логов
            formatted_amount = amount / 10**6
            logger.info(
                f"{self.account_index} | Depositing {formatted_amount:.6f} USDC to Teko Finance..."
            )

            # Format the amount as hex, используя 8 символов
            hex_amount = hex(amount)[2:].zfill(8)

            # Format wallet address without 0x
            wallet_address_no_prefix = self.wallet.address[2:].lower()

            # Construct the payload
            payload = f"0x8dbdbe6d57841b7b735a58794b8d4d8c38644050529cec291846e80e5afa791048c9410a00000000000000000000000000000000000000000000000000000000{hex_amount}000000000000000000000000{wallet_address_no_prefix}"

            # Contract address for deposit
            contract_address = Web3.to_checksum_address(
                "0x13c051431753fCE53eaEC02af64A38A273E198D0"
            )

            # Prepare nonce
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)

            # Подготовка транзакции
            base_tx = {
                "from": self.wallet.address,
                "to": contract_address,
                "data": payload,
                "value": 0,
                "nonce": nonce,
                "chainId": CHAIN_ID,
            }

            # Попробуем оценить газ, но если будет ошибка, используем фиксированное значение
            try:
                # Получаем цену газа
                gas_price = await self.web3.web3.eth.gas_price
                base_tx["gasPrice"] = gas_price

                # Оцениваем газ
                estimated_gas = await self.web3.web3.eth.estimate_gas(base_tx)
                base_tx["gas"] = int(estimated_gas * 1.2)
            except Exception:
                # Используем фиксированное значение
                base_tx["gas"] = 127769

            # Sign transaction
            signed_tx = self.web3.web3.eth.account.sign_transaction(
                base_tx, self.private_key
            )

            # Send transaction
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
            tx_hex = tx_hash.hex()

            # Wait for transaction receipt
            logger.info(f"{self.account_index} | Waiting for deposit confirmation...")
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash)

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Successfully staked {formatted_amount:.6f} USDC in Teko Finance! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Failed to stake USDC in Teko Finance."
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Staking failed: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def unstake(self):
        try:
            logger.info(f"{self.account_index} | Withdrawing from Teko Finance...")

            # Контракт для вывода средств
            contract_address = Web3.to_checksum_address(
                "0x13c051431753fCE53eaEC02af64A38A273E198D0"
            )

            # Правильный ID пула для tkUSDC
            tkUSDC_pool_id = 39584631314667805491088689848282554447608744687563418855093496965842959155466

            # ABI для функций получения баланса и вывода
            abi = [
                {
                    "type": "function",
                    "name": "getAssetsOf",
                    "inputs": [
                        {"name": "poolId", "type": "uint256"},
                        {"name": "guy", "type": "address"},
                    ],
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                },
                {
                    "type": "function",
                    "name": "withdraw",
                    "inputs": [
                        {"name": "poolId", "type": "uint256"},
                        {"name": "assets", "type": "uint256"},
                        {"name": "receiver", "type": "address"},
                        {"name": "owner", "type": "address"},
                    ],
                    "outputs": [{"name": "shares", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                },
            ]

            contract = self.web3.web3.eth.contract(address=contract_address, abi=abi)

            # Получаем баланс пользователя в пуле
            try:
                balance = await contract.functions.getAssetsOf(
                    tkUSDC_pool_id, self.wallet.address
                ).call()

                # Форматируем баланс для отображения
                formatted_balance = balance / 10**6

                if balance == 0:
                    logger.warning(
                        f"{self.account_index} | No tkUSDC available to withdraw"
                    )
                    return False

                logger.info(
                    f"{self.account_index} | Available tkUSDC for withdrawal: {formatted_balance:.6f} USDC"
                )

                # Выводим доступный баланс
                return await self._withdraw_tkUSDC(contract, tkUSDC_pool_id, balance)

            except Exception as e:
                logger.error(f"{self.account_index} | Withdrawal failed: {e}")
                return False

        except Exception as e:
            logger.error(f"{self.account_index} | Withdrawal failed: {e}")
            return False

    @retry_async(default_value=False)
    async def _withdraw_tkUSDC(self, contract, pool_id, amount):
        try:
            # Форматируем сумму для логов
            formatted_amount = amount / 10**6
            logger.info(
                f"{self.account_index} | Withdrawing {formatted_amount:.6f} USDC from Teko Finance..."
            )

            # Получаем nonce
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)

            # Получаем текущую цену газа
            gas_price = await self.web3.web3.eth.gas_price
            logger.info(
                f"{self.account_index} | Current gas price: {gas_price / 10**9:.9f} Gwei"
            )

            # Создаем базовую транзакцию без газа
            base_tx = {"from": self.wallet.address, "nonce": nonce, "chainId": CHAIN_ID}

            # Если сеть поддерживает EIP-1559, используем maxFeePerGas и maxPriorityFeePerGas
            if hasattr(self.web3.web3.eth, "max_priority_fee"):
                try:
                    # Получаем максимальный приоритетный сбор
                    max_priority_fee = await self.web3.web3.eth.max_priority_fee

                    # Устанавливаем maxFeePerGas и maxPriorityFeePerGas
                    base_tx["maxPriorityFeePerGas"] = max_priority_fee
                    base_tx["maxFeePerGas"] = max_priority_fee + (gas_price * 2)

                    logger.info(
                        f"{self.account_index} | Using EIP-1559 gas: maxPriorityFeePerGas={max_priority_fee / 10**9:.9f} Gwei, maxFeePerGas={(max_priority_fee + (gas_price * 2)) / 10**9:.9f} Gwei"
                    )
                except Exception as e:
                    # Если не удалось получить max_priority_fee, используем обычный gasPrice
                    logger.warning(
                        f"{self.account_index} | Failed to get max_priority_fee: {e}. Using standard gasPrice."
                    )
                    base_tx["gasPrice"] = gas_price
            else:
                # Если сеть не поддерживает EIP-1559, используем обычный gasPrice
                base_tx["gasPrice"] = gas_price

            # Подготавливаем данные для функции вывода
            # withdraw(poolId, assets, receiver, owner)
            func_call = contract.functions.withdraw(
                pool_id,  # Правильный Pool ID для tkUSDC
                amount,  # Количество токенов для вывода
                self.wallet.address,  # Receiver (куда выводим)
                self.wallet.address,  # Owner (владелец токенов)
            )

            # Динамически оцениваем газ для транзакции
            try:
                # Добавляем to в транзакцию для оценки газа
                est_tx = {**base_tx, "to": contract.address}

                # Получаем данные для транзакции
                tx_data = func_call.build_transaction(est_tx)

                # Оцениваем газ
                estimated_gas = await self.web3.web3.eth.estimate_gas(tx_data)

                # Добавляем запас газа (20%)
                gas_limit = int(estimated_gas * 1.2)
                logger.info(
                    f"{self.account_index} | Estimated gas: {estimated_gas}, with 20% buffer: {gas_limit}"
                )

                # Добавляем газ в базовую транзакцию
                base_tx["gas"] = gas_limit

            except Exception as e:
                # Если не удалось оценить газ, используем достаточно большое значение
                fallback_gas = 250000
                logger.warning(
                    f"{self.account_index} | Failed to estimate gas: {e}. Using fallback value: {fallback_gas}"
                )
                base_tx["gas"] = fallback_gas

            # Теперь строим полную транзакцию
            tx = func_call.build_transaction(base_tx)

            # Подписываем транзакцию
            signed_tx = self.web3.web3.eth.account.sign_transaction(
                tx, self.private_key
            )

            # Отправляем транзакцию
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_tx.raw_transaction
            )
            tx_hex = tx_hash.hex()

            # Ждем подтверждения транзакции
            logger.info(
                f"{self.account_index} | Waiting for withdrawal confirmation... TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
            )
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash)

            # Подсчитываем стоимость газа для информации
            gas_used = receipt["gasUsed"]
            gas_cost_wei = gas_used * (
                tx.get("gasPrice") or tx.get("maxFeePerGas", gas_price)
            )
            gas_cost_eth = gas_cost_wei / 10**18

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Successfully withdrawn {formatted_amount:.6f} USDC from Teko Finance! "
                    f"Gas used: {gas_used} (Cost: {gas_cost_eth:.8f} ETH) TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Failed to withdraw USDC from Teko Finance. "
                    f"Gas used: {gas_used} (Cost: {gas_cost_eth:.8f} ETH) TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Withdrawal failed: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def borrow(self):
        try:
            logger.info(f"{self.account_index} | Borrowing from Teko Finance...")

            # Contract address for Teko Finance
            contract_address = Web3.to_checksum_address(
                "0x13c051431753fCE53eaEC02af64A38A273E198D0"
            )

            # We'll use the tkUSDC pool for borrowing
            pool_id = 39584631314667805491088689848282554447608744687563418855093496965842959155466

            # Get token balance for tkETH to use as collateral
            tk_eth_address = Web3.to_checksum_address(
                "0x176735870dc6C22B4EBFBf519DE2ce758de78d94"
            )

            # First check if we have already approved tkETH
            tk_eth_contract = self.web3.web3.eth.contract(
                address=tk_eth_address,
                abi=[
                    {
                        "constant": True,
                        "inputs": [
                            {"name": "_owner", "type": "address"},
                            {"name": "_spender", "type": "address"},
                        ],
                        "name": "allowance",
                        "outputs": [{"name": "remaining", "type": "uint256"}],
                        "type": "function",
                    },
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "_spender", "type": "address"},
                            {"name": "_value", "type": "uint256"},
                        ],
                        "name": "approve",
                        "outputs": [{"name": "success", "type": "bool"}],
                        "type": "function",
                    },
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function",
                    },
                ],
            )

            # Check tkETH balance
            tk_eth_balance = await tk_eth_contract.functions.balanceOf(
                self.wallet.address
            ).call()

            formatted_eth_balance = tk_eth_balance / 10**18
            logger.info(
                f"{self.account_index} | Current tkETH balance: {formatted_eth_balance:.6f} ETH"
            )

            if tk_eth_balance == 0:
                logger.warning(
                    f"{self.account_index} | No tkETH balance to use as collateral"
                )
                return False

            # Approve tkETH for spending if needed
            allowance = await tk_eth_contract.functions.allowance(
                self.wallet.address, contract_address
            ).call()

            if allowance < tk_eth_balance:
                logger.info(
                    f"{self.account_index} | Approving tkETH for Teko Finance..."
                )

                # Get gas parameters properly
                gas_params = await self.web3.get_gas_params()
                if gas_params is None:
                    raise Exception("Failed to get gas parameters")

                approve_tx = await tk_eth_contract.functions.approve(
                    contract_address, 2**256 - 1  # Max approval
                ).build_transaction(
                    {
                        "from": self.wallet.address,
                        "nonce": await self.web3.web3.eth.get_transaction_count(
                            self.wallet.address
                        ),
                        "chainId": CHAIN_ID,
                        **gas_params,  # Use proper gas parameters from web3_custom
                    }
                )

                # Estimate gas
                try:
                    gas_limit = await self.web3.estimate_gas(approve_tx)
                    approve_tx["gas"] = gas_limit
                except Exception as e:
                    logger.warning(
                        f"{self.account_index} | Error estimating gas: {e}. Using default gas limit"
                    )
                    approve_tx["gas"] = 200000  # Default gas limit for approvals

                # Execute the approval transaction
                await self.web3.execute_transaction(
                    tx_data=approve_tx,
                    wallet=self.wallet,
                    chain_id=CHAIN_ID,
                    explorer_url=EXPLORER_URL_MEGAETH,
                )

            # Now deposit tkETH as collateral
            amount_to_deposit = int(
                tk_eth_balance * 0.9
            )  # Use 90% of balance as collateral
            formatted_deposit = amount_to_deposit / 10**18

            logger.info(
                f"{self.account_index} | Depositing {formatted_deposit:.6f} tkETH as collateral..."
            )

            # Check if we have enough ETH to proceed
            eth_balance = await self.web3.get_balance(self.wallet.address)
            logger.info(
                f"{self.account_index} | Current ETH balance: {eth_balance.ether} ETH"
            )

            # Store the updated ABI directly in the code - include all necessary functions
            pool_abi = [
                # Deposit function
                {
                    "type": "function",
                    "name": "deposit",
                    "inputs": [
                        {"name": "poolId", "type": "uint256"},
                        {"name": "assets", "type": "uint256"},
                        {"name": "receiver", "type": "address"},
                    ],
                    "outputs": [{"name": "shares", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                },
                # Borrow function
                {
                    "type": "function",
                    "name": "borrow",
                    "inputs": [
                        {"name": "poolId", "type": "uint256"},
                        {"name": "position", "type": "address"},
                        {"name": "amt", "type": "uint256"},
                    ],
                    "outputs": [{"name": "borrowShares", "type": "uint256"}],
                    "stateMutability": "nonpayable",
                },
                # Accrue function - IMPORTANT TO CALL BEFORE OPERATIONS
                {
                    "type": "function",
                    "name": "accrue",
                    "inputs": [{"name": "id", "type": "uint256"}],
                    "outputs": [],
                    "stateMutability": "nonpayable",
                },
                # getAssetsOf function for checking balance
                {
                    "type": "function",
                    "name": "getAssetsOf",
                    "inputs": [
                        {"name": "poolId", "type": "uint256"},
                        {"name": "guy", "type": "address"},
                    ],
                    "outputs": [{"name": "", "type": "uint256"}],
                    "stateMutability": "view",
                },
            ]

            # Create contract instance for lending pool
            pool_contract = self.web3.web3.eth.contract(
                address=contract_address, abi=pool_abi
            )

            # Get ETH pool ID where we'll deposit our collateral
            eth_pool_id = 72572175584673509244743384162953726919624465952543019256792130552168516108177

            # First, accrue interest for the pool before any operation
            try:
                logger.info(
                    f"{self.account_index} | Accruing interest for the pool before deposit..."
                )

                # Get gas parameters
                gas_params = await self.web3.get_gas_params()
                if gas_params is None:
                    raise Exception("Failed to get gas parameters")

                # Get current nonce
                nonce = await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                )

                # Build accrue transaction
                accrue_tx = await pool_contract.functions.accrue(
                    eth_pool_id  # Pool ID for tkETH
                ).build_transaction(
                    {
                        "from": self.wallet.address,
                        "nonce": nonce,
                        "chainId": CHAIN_ID,
                        "gas": 200000,  # Conservative gas limit
                        **gas_params,
                    }
                )

                # Execute the accrue transaction
                accrue_tx_hash = await self.web3.execute_transaction(
                    tx_data=accrue_tx,
                    wallet=self.wallet,
                    chain_id=CHAIN_ID,
                    explorer_url=EXPLORER_URL_MEGAETH,
                )

                if not accrue_tx_hash:
                    logger.warning(
                        f"{self.account_index} | Accrue transaction failed, but we'll try to continue..."
                    )
                else:
                    logger.success(
                        f"{self.account_index} | Successfully accrued interest for the pool"
                    )
                    # Wait a moment for the transaction to be processed
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning(
                    f"{self.account_index} | Error accruing interest, but we'll try to continue: {e}"
                )

            # Now proceed with deposit
            # Get fresh gas parameters and nonce
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)

            # Build deposit transaction (use lower gas estimate to save ETH)
            deposit_tx = await pool_contract.functions.deposit(
                eth_pool_id,  # Pool ID for tkETH
                amount_to_deposit,  # Amount to deposit
                self.wallet.address,  # Receiver
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    "chainId": CHAIN_ID,
                    "gas": 200000,  # Reduced gas limit to save ETH
                    **gas_params,
                }
            )

            # Execute the deposit transaction
            deposit_tx_hash = await self.web3.execute_transaction(
                tx_data=deposit_tx,
                wallet=self.wallet,
                chain_id=CHAIN_ID,
                explorer_url=EXPLORER_URL_MEGAETH,
            )

            if not deposit_tx_hash:
                logger.error(f"{self.account_index} | Failed to deposit collateral")
                return False

            logger.success(
                f"{self.account_index} | Successfully deposited {formatted_deposit:.6f} tkETH as collateral"
            )

            # Wait a moment for the deposit to be processed
            await asyncio.sleep(2)

            # Now borrow a very small amount of tkUSDC to ensure we have enough ETH for gas
            # Using a much smaller amount to ensure success
            borrow_amount = 500_000  # 0.5 USDC with 6 decimals
            formatted_borrow = borrow_amount / 10**6

            logger.info(
                f"{self.account_index} | Borrowing {formatted_borrow:.2f} USDC from Teko Finance..."
            )

            # First, accrue interest for the USDC pool before borrowing
            try:
                logger.info(
                    f"{self.account_index} | Accruing interest for the USDC pool before borrowing..."
                )

                # Get fresh nonce
                nonce = await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                )

                # Build accrue transaction for USDC pool
                accrue_tx = await pool_contract.functions.accrue(
                    pool_id  # Pool ID for tkUSDC
                ).build_transaction(
                    {
                        "from": self.wallet.address,
                        "nonce": nonce,
                        "chainId": CHAIN_ID,
                        "gas": 200000,  # Conservative gas limit
                        **gas_params,
                    }
                )

                # Execute the accrue transaction
                accrue_tx_hash = await self.web3.execute_transaction(
                    tx_data=accrue_tx,
                    wallet=self.wallet,
                    chain_id=CHAIN_ID,
                    explorer_url=EXPLORER_URL_MEGAETH,
                )

                if not accrue_tx_hash:
                    logger.warning(
                        f"{self.account_index} | Accrue transaction for USDC pool failed, but we'll try to continue..."
                    )
                else:
                    logger.success(
                        f"{self.account_index} | Successfully accrued interest for the USDC pool"
                    )
                    # Wait a moment for the transaction to be processed
                    await asyncio.sleep(2)

            except Exception as e:
                logger.warning(
                    f"{self.account_index} | Error accruing interest for USDC pool, but we'll try to continue: {e}"
                )

            # Get fresh nonce and gas parameters
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Build borrow transaction with lower gas estimate
            borrow_tx = await pool_contract.functions.borrow(
                pool_id,  # Pool ID for tkUSDC
                self.wallet.address,  # Position (borrower)
                borrow_amount,  # Amount to borrow (reduced)
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    "chainId": CHAIN_ID,
                    "gas": 300000,  # Reduced gas limit
                    **gas_params,
                }
            )

            # Execute the borrow transaction
            borrow_tx_hash = await self.web3.execute_transaction(
                tx_data=borrow_tx,
                wallet=self.wallet,
                chain_id=CHAIN_ID,
                explorer_url=EXPLORER_URL_MEGAETH,
            )

            if not borrow_tx_hash:
                logger.error(f"{self.account_index} | Failed to borrow USDC")
                return False

            logger.success(
                f"{self.account_index} | Successfully borrowed {formatted_borrow:.2f} USDC from Teko Finance!"
            )
            return True

        except Exception as e:
            logger.error(f"{self.account_index} | Borrowing failed: {e}")
            return False


ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function",
    }
]

TK_USDC_ADDRESS = "0xFaf334e157175Ff676911AdcF0964D7f54F2C424"
