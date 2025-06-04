import asyncio
import random
import hashlib
import time
import os

from eth_account import Account
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
from web3 import Web3
from src.utils.decorators import retry_async
from src.utils.config import Config
from src.utils.constants import EXPLORER_URL_MEGAETH

CHAIN_ID = 6342  # From constants.py comment


class XLMeme:
    def __init__(
        self,
        account_index: int,
        session: primp.AsyncClient,
        web3: Web3Custom,
        config: Config,
        wallet: Account,
    ):
        self.account_index = account_index
        self.session = session
        self.web3 = web3
        self.config = config
        self.wallet = wallet

    async def buy_meme(self):
        try:
            # Теперь мы понимаем, что CONTRACTS_TO_BUY это адреса токенов, а не бондинговых кривых
            # Нам нужно получить адрес бондинговой кривой для выбранного токена
            if len(self.config.MINTS.XL_MEME.CONTRACTS_TO_BUY) > 0:
                random_token_contract = random.choice(
                    self.config.MINTS.XL_MEME.CONTRACTS_TO_BUY
                )
            else:
                random_token_contract = await self._get_random_token_for_mint()
                if not random_token_contract:
                    logger.error(
                        f"{self.account_index} | Failed to get random token for mint"
                    )
                    return False

            bonding_curve_address = await self._get_bonding_curve_address(
                random_token_contract
            )

            if not bonding_curve_address:
                logger.error(
                    f"{self.account_index} | Failed to get bonding curve address for token: {random_token_contract}"
                )
                return False

            random_balance_percentage = random.choice(
                self.config.MINTS.XL_MEME.BALANCE_PERCENTAGE_TO_BUY
            )

            balance = await self.web3.get_balance(self.wallet.address)

            # Рассчитываем сумму в ETH (для логирования)
            amount_in_eth = balance.ether * random_balance_percentage / 100

            # Устанавливаем минимальную сумму для транзакции в ETH
            min_amount_eth = 0.0000001
            if amount_in_eth < min_amount_eth:
                random_min_balance = random.uniform(0.0000001, 0.000005)
                logger.info(
                    f"{self.account_index} | Calculated amount {amount_in_eth} ETH is too small, using minimum amount {random_min_balance} ETH"
                )
                amount_in_eth = random_min_balance

            # Конвертируем в wei для транзакции
            amount_in_wei = Web3.to_wei(amount_in_eth, "ether")

            # Проверяем, что у нас достаточно ETH для транзакции
            if balance.wei < amount_in_wei:
                logger.error(
                    f"{self.account_index} | Not enough ETH for mint. Required: {amount_in_eth:.8f} ETH, Available: {balance.ether:.8f} ETH"
                )
                return False

            return await self._buy(bonding_curve_address, amount_in_wei)
        except Exception as e:
            logger.error(f"{self.account_index} | Failed to buy meme on XLMeme: {e}")
            return False

    @retry_async(default_value=False)
    async def _buy(self, contract_address: str, amount: int):
        try:
            # Создаем контракт с минимальным ABI для функций buyForETH и estimateBuy
            contract_abi = [
                {
                    "inputs": [
                        {"name": "buyer", "type": "address", "internalType": "address"},
                        {
                            "name": "reserveAmountIn",
                            "type": "uint256",
                            "internalType": "uint256",
                        },
                        {
                            "name": "supplyAmountOutMin",
                            "type": "uint256",
                            "internalType": "uint256",
                        },
                    ],
                    "name": "buyForETH",
                    "outputs": [
                        {"name": "", "type": "uint256", "internalType": "uint256"}
                    ],
                    "stateMutability": "payable",
                    "type": "function",
                },
                {
                    "inputs": [
                        {
                            "name": "reserveAmountIn",
                            "type": "uint256",
                            "internalType": "uint256",
                        }
                    ],
                    "name": "estimateBuy",
                    "outputs": [
                        {"name": "", "type": "uint256", "internalType": "uint256"}
                    ],
                    "stateMutability": "view",
                    "type": "function",
                },
            ]

            contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(contract_address),
                abi=contract_abi,
            )

            # Убедимся, что amount - целое число
            amount = int(amount)

            # Используем метод estimateBuy для получения ожидаемого количества токенов
            try:
                estimated_tokens = await contract.functions.estimateBuy(amount).call()
                # Используем 95% от ожидаемого количества токенов для учета проскальзывания
                supply_amount_out_min = int(estimated_tokens * 0.95)
            except Exception as e:
                logger.warning(
                    f"{self.account_index} | Failed to estimate buy amount: {str(e)}. Using default slippage."
                )
                # Если не удалось получить оценку, используем значение по умолчанию (75% от суммы)
                supply_amount_out_min = int(amount * 0.75)

            logger.info(
                f"{self.account_index} | Buying {contract_address} for {Web3.from_wei(amount, 'ether'):.8f} ETH"
            )

            # Создаем базовую транзакцию с минимальными настройками
            # Для асинхронного Web3 нужно использовать другой подход
            tx = await contract.functions.buyForETH(
                self.wallet.address, amount, supply_amount_out_min
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "value": amount,
                    "chainId": CHAIN_ID,
                    "nonce": await self.web3.web3.eth.get_transaction_count(
                        self.wallet.address
                    ),
                }
            )

            # Теперь очистим все потенциально конфликтующие параметры газа
            if "maxFeePerGas" in tx:
                del tx["maxFeePerGas"]
            if "maxPriorityFeePerGas" in tx:
                del tx["maxPriorityFeePerGas"]

            # Добавим только gasPrice
            gas_price = await self.web3.web3.eth.gas_price
            tx["gasPrice"] = int(gas_price * 1.1)  # Увеличиваем на 10%

            # Оцениваем газ
            try:
                tx_for_estimate = tx.copy()
                estimated_gas = await self.web3.web3.eth.estimate_gas(tx_for_estimate)
                tx["gas"] = int(
                    estimated_gas * 1.3
                )  # Увеличиваем на 30% для безопасности
            except Exception as e:
                raise e

            # Подписываем и отправляем транзакцию
            signed_txn = self.web3.web3.eth.account.sign_transaction(
                tx, self.wallet.key
            )
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_txn.raw_transaction
            )
            tx_hash_hex = tx_hash.hex()

            # Ждем завершения транзакции
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=60
            )

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Mint successfully completed: {EXPLORER_URL_MEGAETH}{tx_hash_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Transaction failed: {tx_hash_hex}"
                )
                return False

        except Exception as e:
            logger.error(f"{self.account_index} | Error executing mint: {str(e)}")
            return False

    @retry_async(default_value=None)
    async def _get_bonding_curve_address(self, token_contract: str) -> str:
        try:
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                "origin": "https://testnet.xlmeme.com",
                "priority": "u=1, i",
                "referer": "https://testnet.xlmeme.com/",
                "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            }

            params = {
                "page": "1",
                "page_size": "50",
            }

            response = await self.session.get(
                f"https://api-testnet.xlmeme.com/api/statistics/megaeth_testnet/1min/bonding-curve/{token_contract}/",
                params=params,
                headers=headers,
            )
            if response.json()["count"] != 0:
                return response.json()["results"][0]["bonding_curve_address"]

            response = await self.session.get(
                f"https://api-testnet.xlmeme.com/api/tokens/network/megaeth_testnet/{token_contract}/",
                headers=headers,
            )
            contract_uuid = response.json()["uuid"]

            response = await self.session.get(
                f"https://api-testnet.xlmeme.com/api/bonding-curves/token/{contract_uuid}/",
                headers=headers,
            )
            return response.json()["address"]
        except Exception as e:
            logger.error(
                f"{self.account_index} | Error parsing mint contract address: {str(e)}"
            )
            raise e

    @retry_async(default_value=None)
    async def _get_random_token_for_mint(self) -> str:
        try:
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                "origin": "https://testnet.xlmeme.com",
                "priority": "u=1, i",
                "referer": "https://testnet.xlmeme.com/",
                "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            }

            params = {
                "page": "1",
                "search": "",
                "ordering": "-market_cap_xlm",
                "page_size": "50",
                "creator_wallet_address": "",
                "blockchain": "megaeth_testnet",
            }

            response = await self.session.get(
                "https://api-testnet.xlmeme.com/api/tokens/",
                params=params,
                headers=headers,
            )

            contracts = response.json()["results"]
            random_contract = random.choice(contracts)

            logger.info(
                f"{self.account_index} | Will try to mint token {random_contract['ticker']} | {random_contract['contract_address']} "
            )
            return random_contract["contract_address"]

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error getting random token for mint: {str(e)}"
            )
            raise e
