import random
from eth_account.messages import encode_typed_data
from eth_account import Account
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
from web3 import Web3
from curl_cffi.requests import AsyncSession
import time
import asyncio
from eth_account.messages import encode_defunct

from src.utils.decorators import retry_async
from src.utils.config import Config
from src.utils.constants import EXPLORER_URL_MEGAETH


CHAIN_ID = 6342  # From constants.py comment
TOKEN_FACTORY_ADDRESS = Web3.to_checksum_address(
    "0x6B82b7BB668dA9EF1834896b1344Ac34B06fc58D"
)

TOKEN_FACTORY_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "tokenAddress", "type": "address"},
            {"internalType": "uint256", "name": "tokenAmount", "type": "uint256"},
            {"internalType": "address", "name": "to", "type": "address"},
        ],
        "name": "buyExactOut",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function",
    }
]

# Minimal ERC20 ABI for balanceOf and approve
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
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
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"name": "remaining", "type": "uint256"}],
        "type": "function",
    },
]


class Rainmakr:
    def __init__(
        self,
        account_index: int,
        session: primp.AsyncClient,
        web3: Web3Custom,
        config: Config,
        wallet: Account,
        private_key: str,
    ):
        self.account_index = account_index
        self.session = session
        self.web3 = web3
        self.config = config
        self.wallet = wallet
        self.private_key = private_key

        self.bearer_token = ""
        self.contract = self.web3.web3.eth.contract(
            address=self.web3.web3.to_checksum_address(TOKEN_FACTORY_ADDRESS),
            abi=TOKEN_FACTORY_ABI,
        )

    async def buy_meme(self):
        try:
            if not await self._get_bearer_token():
                logger.error(f"{self.account_index} | Failed to get bearer token")
                return False
            logger.info(f"{self.account_index} | Bearer token received")

            # Теперь мы понимаем, что CONTRACTS_TO_BUY это адреса токенов, а не бондинговых кривых
            # Нам нужно получить адрес бондинговой кривой для выбранного токена
            if len(self.config.MINTS.RAINMAKR.CONTRACTS_TO_BUY) > 0:
                random_token_contract = random.choice(
                    self.config.MINTS.RAINMAKR.CONTRACTS_TO_BUY
                )
            else:
                random_token_contract = await self._get_random_token_for_mint()
                if not random_token_contract:
                    logger.error(
                        f"{self.account_index} | Failed to get random token for mint"
                    )
                    return False

            random_amount_of_eth_to_buy = random.uniform(
                self.config.MINTS.RAINMAKR.AMOUNT_OF_ETH_TO_BUY[0],
                self.config.MINTS.RAINMAKR.AMOUNT_OF_ETH_TO_BUY[1],
            )

            balance = await self.web3.get_balance(self.wallet.address)

            # Convert to ETH for logging and comparison
            amount_in_eth = random_amount_of_eth_to_buy

            # Check if we have enough balance
            if balance.ether < amount_in_eth:
                logger.error(
                    f"{self.account_index} | Not enough ETH for mint. Required: {amount_in_eth:.8f} ETH, Available: {balance.ether:.8f} ETH"
                )
                return False

            # Convert to wei for transaction
            amount_in_wei = Web3.to_wei(amount_in_eth, "ether")

            if not await self._buy(random_token_contract, amount_in_wei):
                logger.error(
                    f"{self.account_index} | Failed to buy meme on Rainmakr: {random_token_contract}"
                )
                return False

            random_pause = random.randint(15, 30)
            # Wait a bit before selling
            logger.info(
                f"{self.account_index} | Waiting {random_pause} seconds before selling tokens..."
            )
            await asyncio.sleep(random_pause)

            # Sell the tokens
            if not await self._sell(random_token_contract):
                logger.error(
                    f"{self.account_index} | Failed to sell tokens: {random_token_contract}"
                )
                return False

            logger.success(
                f"{self.account_index} | Successfully completed buy and sell of {random_token_contract}"
            )
            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Failed to buy meme on Rainmakr: {e}")
            return False

    @retry_async(default_value=False)
    async def _buy(self, contract_address: str, amount: int):
        try:
            # Create payload with token address and user address (both without 0x prefix)
            payload = f"0xb909e38b000000000000000000000000{contract_address[2:]}0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000{self.wallet.address[2:]}"

            # Убедимся, что amount - целое число
            amount = int(amount)

            logger.info(
                f"{self.account_index} | Buying {contract_address} for {Web3.from_wei(amount, 'ether'):.8f} ETH"
            )

            # Create transaction
            tx = {
                "from": self.wallet.address,
                "to": TOKEN_FACTORY_ADDRESS,  # Send to TOKEN_FACTORY_ADDRESS
                "value": amount,  # Amount of ETH to spend
                "data": payload,  # Our payload with token address and wallet address
                "chainId": CHAIN_ID,
                "nonce": await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                ),
            }

            # Get gas price
            gas_price = await self.web3.web3.eth.gas_price
            tx["gasPrice"] = int(gas_price * 1.1)  # Увеличиваем на 10%

            # Estimate gas
            try:
                tx_for_estimate = tx.copy()
                estimated_gas = await self.web3.web3.eth.estimate_gas(tx_for_estimate)
                tx["gas"] = int(
                    estimated_gas * 1.3
                )  # Увеличиваем на 30% для безопасности
            except Exception as e:
                raise e

            # Sign and send transaction
            signed_txn = self.web3.web3.eth.account.sign_transaction(
                tx, self.private_key
            )
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_txn.raw_transaction
            )
            tx_hash_hex = tx_hash.hex()

            # Wait for transaction receipt
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=60
            )

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Token purchase successfully completed: {EXPLORER_URL_MEGAETH}{tx_hash_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Transaction failed: {tx_hash_hex}"
                )
                return False

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error executing token purchase: {str(e)}"
            )
            return False

    @retry_async(default_value=False)
    async def _sell(self, contract_address: str):
        try:
            # Create ERC20 contract instance to check balance
            token_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(contract_address),
                abi=ERC20_ABI,
            )

            # Get token balance for the wallet
            token_balance = await token_contract.functions.balanceOf(
                self.wallet.address
            ).call()

            if token_balance == 0:
                logger.warning(
                    f"{self.account_index} | No tokens to sell on {contract_address}"
                )
                return False

            # Конвертируем баланс в читаемый формат (предполагая 18 знаков)
            try:
                token_balance_ether = Web3.from_wei(token_balance, "ether")
            except Exception:
                token_balance_ether = token_balance  # Если не удалось, покажем как есть

            # IMPORTANT: First approve the TOKEN_FACTORY_ADDRESS to spend tokens
            # Check current allowance
            current_allowance = await token_contract.functions.allowance(
                self.wallet.address, TOKEN_FACTORY_ADDRESS
            ).call()

            # Use actual token balance, not a fixed amount
            token_amount = token_balance  # Для транзакции используем сырое значение
            token_amount_hex = hex(token_amount)[2:]

            # Корректное форматирование всех параметров до 32 байт (64 hex символа)
            token_address_part = contract_address[2:].lower().zfill(64)
            token_amount_hex = token_amount_hex.zfill(64)
            # Используем адрес из рабочего примера, не адрес кошелька
            final_address_part = "4c4c1b866b433860366f93dc4135a0250cccdcfa".zfill(64)
            # Добавляем паддинг из нулей между суммой и последним адресом, как в рабочем примере
            zero_padding = "0".zfill(64)

            logger.info(
                f"{self.account_index} | Using actual token balance for selling: {token_balance_ether:.8f} tokens"
            )
            logger.info(
                f"{self.account_index} | Current allowance: {current_allowance}"
            )

            # If allowance is insufficient, approve tokens
            if current_allowance < token_amount:
                logger.info(
                    f"{self.account_index} | Approving tokens to be spent by the exchange contract"
                )

                # Use max uint256 for unlimited approval
                max_approval = 2**256 - 1

                # Create approval transaction
                approval_tx = await token_contract.functions.approve(
                    TOKEN_FACTORY_ADDRESS, max_approval
                ).build_transaction(
                    {
                        "from": self.wallet.address,
                        "chainId": CHAIN_ID,
                        "nonce": await self.web3.web3.eth.get_transaction_count(
                            self.wallet.address
                        ),
                        "gasPrice": await self.web3.web3.eth.gas_price,
                    }
                )

                # Estimate gas
                try:
                    gas_estimate = await self.web3.web3.eth.estimate_gas(approval_tx)
                    approval_tx["gas"] = int(gas_estimate * 1.3)
                except Exception as e:
                    raise e

                # Sign and send approval transaction
                signed_approval = self.web3.web3.eth.account.sign_transaction(
                    approval_tx, self.private_key
                )
                approval_hash = await self.web3.web3.eth.send_raw_transaction(
                    signed_approval.raw_transaction
                )

                # Wait for approval transaction to complete
                approval_receipt = (
                    await self.web3.web3.eth.wait_for_transaction_receipt(approval_hash)
                )

                if approval_receipt["status"] == 1:
                    logger.success(
                        f"{self.account_index} | Token approval successful: {EXPLORER_URL_MEGAETH}{approval_hash.hex()}"
                    )
                else:
                    logger.error(f"{self.account_index} | Token approval failed")
                    return False

                # Wait a bit after approval
                await asyncio.sleep(5)

            # Now proceed with the sell transaction using the actual token balance
            # Create payload using correctly formatted parameters (each 64 chars) + zero padding
            function_selector = "0x0a7f0c9d"
            payload = f"{function_selector}{token_address_part}{token_amount_hex}{zero_padding}{final_address_part}"

            logger.info(
                f"{self.account_index} | Selling {token_balance_ether:.8f} tokens from {contract_address}"
            )

            # Create transaction
            tx = {
                "from": self.wallet.address,
                "to": TOKEN_FACTORY_ADDRESS,
                "value": 0,  # No ETH value
                "data": payload,
                "chainId": CHAIN_ID,
                "nonce": await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                ),
            }

            # Get gas price
            gas_price = await self.web3.web3.eth.gas_price
            tx["gasPrice"] = int(gas_price * 1.1)  # Увеличиваем на 10%

            # Estimate gas
            try:
                tx_for_estimate = tx.copy()
                estimated_gas = await self.web3.web3.eth.estimate_gas(tx_for_estimate)
                tx["gas"] = int(
                    estimated_gas * 1.3
                )  # Увеличиваем на 30% для безопасности
            except Exception as e:
                raise e

            # Sign and send transaction
            signed_txn = self.web3.web3.eth.account.sign_transaction(
                tx, self.private_key
            )
            tx_hash = await self.web3.web3.eth.send_raw_transaction(
                signed_txn.raw_transaction
            )
            tx_hash_hex = tx_hash.hex()

            # Wait for transaction receipt
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=60
            )

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Token sale successfully completed: {EXPLORER_URL_MEGAETH}{tx_hash_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Transaction failed: {tx_hash_hex}"
                )
                return False

        except Exception as e:
            logger.error(f"{self.account_index} | Error executing token sale: {str(e)}")
            return False

    @retry_async(default_value=None)
    async def _get_random_token_for_mint(self) -> str:
        try:
            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                "authorization": f"Bearer {self.bearer_token}",
                "if-none-match": 'W/"14730-+Xgomu0RunpleDx7jn8c+zUElMA"',
                "origin": "https://rainmakr.xyz",
                "priority": "u=1, i",
                "referer": "https://rainmakr.xyz/",
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
                "limit": "100",
                "mainFilterToken": "TRENDING",
            }

            response = await self.session.get(
                "https://rain-ai.rainmakr.xyz/api/token", params=params, headers=headers
            )
            contracts = response.json()["data"]
            random.shuffle(contracts)

            random_contract = {}
            for contract in contracts:
                try:
                    if int(contract["numberHolder"]) > 5 and "contractAddress" in contract and "name" in contract:
                        random_contract = contract
                        break
                except:
                    pass
            
            logger.info(
                f"{self.account_index} | Will try to mint token {random_contract['name']} | {random_contract['contractAddress']}"
            )
            return random_contract["contractAddress"]

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error getting random token for mint: {str(e)}"
            )
            raise e

    @retry_async(default_value=False)
    async def _get_bearer_token(self):
        try:
            message = "USER_CONNECT_WALLET"
            encoded_msg = encode_defunct(text=message)
            signed_msg = Web3().eth.account.sign_message(
                encoded_msg, private_key=self.private_key
            )
            signature = signed_msg.signature.hex()
            signature = "0x" + signature

            headers = {
                "accept": "application/json, text/plain, */*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                "content-type": "application/json",
                "origin": "https://rainmakr.xyz",
                "priority": "u=1, i",
                "referer": "https://rainmakr.xyz/",
                "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            }

            json_data = {
                "signature": signature,
                "address": self.wallet.address,
            }

            response = await self.session.post(
                "https://rain-ai.rainmakr.xyz/api/auth/connect-wallet",
                headers=headers,
                json=json_data,
            )
            self.bearer_token = response.json()["data"]["access_token"]

            if self.bearer_token:
                return True
            else:
                raise Exception("Failed to get bearer token")

        except Exception as e:
            logger.error(f"{self.account_index} | Error getting bearer token: {str(e)}")
            raise e
