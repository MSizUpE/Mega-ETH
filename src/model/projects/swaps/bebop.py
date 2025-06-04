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

# Contract addresses
WETH_CONTRACT = Web3.to_checksum_address("0x4eb2bd7bee16f38b1f4a0a5796fffd028b6040e9")
SPENDER_CONTRACT = Web3.to_checksum_address(
    "0x000000000022D473030F116dDEE9F6B43aC78BA3"
)  # Contract to approve for spending WETH
ROUTER_CONTRACT = Web3.to_checksum_address(
    "0xbeb0b0623f66be8ce162ebdfa2ec543a522f4ea6"
)  # Bebop router
CUSD_CONTRACT = Web3.to_checksum_address(
    "0xe9b6e75c243b6100ffcb1c66e8f78f96feea727f"
)  # cUSD token

# ABIs
WETH_ABI = [
    {
        "constant": False,
        "inputs": [],
        "name": "deposit",
        "outputs": [],
        "payable": True,
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [{"name": "wad", "type": "uint256"}],
        "name": "withdraw",
        "outputs": [],
        "type": "function",
    },
]

# ERC20 ABI for approve function
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
    {
        "constant": True,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
]

# Constants
MAX_UINT256 = 2**256 - 1  # Maximum uint256 value for unlimited approval

# Default swap amount in ETH (0.0000006 ETH)
DEFAULT_SWAP_AMOUNT_ETH = 0.0000006


class Bebop:
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

    def _eth_to_wei(self, eth_amount):
        """Convert ETH amount to wei"""
        return int(eth_amount * 10**18)

    async def swaps(self):
        try:
            logger.info(f"{self.account_index} | Starting swap operation at Bebop...")

            # Check WETH balance
            weth_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(WETH_CONTRACT), abi=WETH_ABI
            )
            weth_balance_wei = await weth_contract.functions.balanceOf(
                self.wallet.address
            ).call()
            weth_balance = weth_balance_wei / 10**18

            logger.info(f"{self.account_index} | WETH balance: {weth_balance} WETH")

            # Get ETH balance
            eth_balance_wei = await self.web3.web3.eth.get_balance(self.wallet.address)
            eth_balance = eth_balance_wei / 10**18

            logger.info(f"{self.account_index} | ETH balance: {eth_balance} ETH")

            # Check if "SWAP_ALL_TO_ETH" is enabled in config
            swap_all_to_eth = self.config.SWAPS.BEBOP.SWAP_ALL_TO_ETH

            # If SWAP_ALL_TO_ETH is true, always sell WETH to ETH if there's any WETH
            if swap_all_to_eth:
                if weth_balance > 0:
                    logger.info(
                        f"{self.account_index} | Config set to swap all WETH to ETH"
                    )
                    # Unwrap all WETH to ETH
                    await self._approve_weth()
                    return await self._unwrap_weth_to_eth(weth_balance)
                else:
                    logger.info(
                        f"{self.account_index} | SWAP_ALL_TO_ETH enabled but no WETH balance. Skipping."
                    )
                    return True

            # Regular swap logic (when SWAP_ALL_TO_ETH is false)
            if weth_balance > 0:
                # If we have WETH, sell all of it
                logger.info(
                    f"{self.account_index} | Found WETH balance. Unwrapping WETH to ETH..."
                )
                await self._approve_weth()
                return await self._unwrap_weth_to_eth(weth_balance)
                
            else:
                # If no WETH, then buy some with a percentage of ETH
                # Get percentage range from config
                percentage_range = self.config.SWAPS.BEBOP.BALANCE_PERCENTAGE_TO_SWAP
                percentage = random.uniform(percentage_range[0], percentage_range[1])

                # Calculate amount to swap (percentage of ETH balance)
                swap_amount = (eth_balance * percentage) / 100

                # Round to 8 decimal places
                swap_amount = round(swap_amount, 8)

                logger.info(
                    f"{self.account_index} | Swapping {swap_amount} ETH ({percentage:.2f}% of balance) to WETH"
                )

                # Check if amount is too small
                if swap_amount < 0.00000001:
                    logger.warning(
                        f"{self.account_index} | Swap amount too small. Using minimum amount."
                    )
                    swap_amount = 0.00000001

                # Step 1: Wrap ETH to WETH
                return await self._swap_eth_to_weth(swap_amount)

        except Exception as e:
            logger.error(f"{self.account_index} | Error swapping tokens at Bebop: {e}")
            return False

    @retry_async(default_value=False)
    async def _check_cusd_balance(self):
        """Check the cUSD balance of the wallet"""
        try:
            logger.info(f"{self.account_index} | Checking cUSD balance...")

            # Create contract instance
            cusd_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(CUSD_CONTRACT), abi=ERC20_ABI
            )

            # Get balance
            balance_wei = await cusd_contract.functions.balanceOf(
                self.wallet.address
            ).call()

            # Convert from wei to cUSD (18 decimals)
            balance_cusd = balance_wei / 10**18

            logger.info(f"{self.account_index} | cUSD balance: {balance_cusd} cUSD")
            return balance_cusd

        except Exception as e:
            logger.error(f"{self.account_index} | Failed to check cUSD balance: {e}")
            return 0

    @retry_async(default_value=False)
    async def _swap_eth_to_weth(self, amount_eth):
        try:
            # Convert ETH to wei
            amount_wei = self._eth_to_wei(amount_eth)

            logger.info(f"{self.account_index} | Wrapping {amount_eth} ETH to WETH...")

            # Create contract instance
            weth_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(WETH_CONTRACT), abi=WETH_ABI
            )

            # Get gas parameters
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Prepare transaction parameters
            tx_params = {
                "from": self.wallet.address,
                "value": amount_wei,
                "nonce": await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                ),
                "chainId": CHAIN_ID,
                **gas_params,
            }

            # Set transaction type based on gas params
            if "maxFeePerGas" in gas_params:
                tx_params["type"] = 2

            # Build transaction using deposit function
            tx = await weth_contract.functions.deposit().build_transaction(tx_params)

            # Execute transaction
            tx_hash = await self.web3.execute_transaction(
                tx,
                wallet=self.wallet,
                chain_id=CHAIN_ID,
                explorer_url=EXPLORER_URL_MEGAETH,
            )

            if tx_hash:
                logger.success(
                    f"{self.account_index} | {amount_eth} ETH wrapped to WETH successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hash}"
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
                f"{self.account_index} | Failed to swap ETH to WETH: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _approve_weth(self):
        try:
            logger.info(f"{self.account_index} | Approving WETH for spending...")

            # Create contract instance
            weth_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(WETH_CONTRACT), abi=WETH_ABI
            )

            # Get gas parameters
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Prepare transaction parameters
            tx_params = {
                "from": self.wallet.address,
                "nonce": await self.web3.web3.eth.get_transaction_count(
                    self.wallet.address
                ),
                "chainId": CHAIN_ID,
                **gas_params,
            }

            # Set transaction type based on gas params
            if "maxFeePerGas" in gas_params:
                tx_params["type"] = 2

            # Build transaction for approving maximum amount
            tx = await weth_contract.functions.approve(
                self.web3.web3.to_checksum_address(SPENDER_CONTRACT), MAX_UINT256
            ).build_transaction(tx_params)

            # Execute transaction
            tx_hash = await self.web3.execute_transaction(
                tx,
                wallet=self.wallet,
                chain_id=CHAIN_ID,
                explorer_url=EXPLORER_URL_MEGAETH,
            )

            if tx_hash:
                logger.success(
                    f"{self.account_index} | WETH approved for spending successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hash}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | WETH approval transaction failed."
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Failed to approve WETH: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _approve_cusd(self):
        try:
            logger.info(f"{self.account_index} | Approving cUSD for spending...")

            # Approve payload from the example transaction
            approve_data = "0x095ea7b3000000000000000000000000000000000022d473030f116ddee9f6b43ac78ba3ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

            # Get gas parameters
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Prepare transaction parameters
            tx = {
                "from": self.wallet.address,
                "to": CUSD_CONTRACT,  # cUSD token contract
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
                    f"{self.account_index} | cUSD approved for spending successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | cUSD approval transaction failed."
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Failed to approve cUSD: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def _unwrap_weth_to_eth(self, amount_eth):
        try:
            # Convert ETH to wei
            amount_wei = self._eth_to_wei(amount_eth)

            logger.info(
                f"{self.account_index} | Unwrapping {amount_eth} ETH worth of WETH to ETH..."
            )

            # Create function selector and encode the amount parameter
            function_selector = "0x2e1a7d4d"  # withdraw(uint256)
            amount_hex = hex(amount_wei)[2:].zfill(
                64
            )  # Convert to hex without '0x' and pad to 64 chars

            # Construct the complete payload
            withdraw_data = function_selector + amount_hex

            # Get gas parameters
            gas_params = await self.web3.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            # Prepare transaction parameters
            tx = {
                "from": self.wallet.address,
                "to": WETH_CONTRACT,  # WETH token contract
                "data": withdraw_data,
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
                logger.warning(
                    f"{self.account_index} | Error estimating gas: {e}. Using default gas limit."
                )
                tx["gas"] = 40000  # Default gas limit for WETH withdraw

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
                    f"{self.account_index} | {amount_eth} ETH worth of WETH unwrapped to ETH successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | WETH to ETH unwrap transaction failed."
                )
                return False

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Failed to unwrap WETH to ETH: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    # async def _swap_cusd_to_weth(self, amount_cusd):
    #     try:
    #         # Convert cUSD amount to wei (1 cUSD = 10^18 wei)
    #         amount_wei = int(amount_cusd * 10**18)

    #         params = {
    #             "partner_id": 0,
    #             "buy_tokens": WETH_CONTRACT,
    #             "sell_tokens": CUSD_CONTRACT,
    #             "taker_address": self.wallet.address,
    #             "gasless": "true",
    #             "receiver_address": self.wallet.address,
    #             "source": "bebop.xyz",
    #             "approval_type": "Permit2",
    #             "sell_amounts": str(amount_wei),  # Convert to string for the API
    #         }
    #         data = await self._get_quote_data(**params)

    #         print(data)  # Print full response for debugging

    #         random_route = random.choice(data["routes"])

    #         # Save the toSign data - this is critical
    #         to_sign_data = random_route["quote"]["toSign"]
    #         print(f"To sign data: {to_sign_data}")

    #         bebop_data = {
    #             "data_to_sign": to_sign_data,
    #             "quote_id": random_route["quote"]["quoteId"],
    #             "route_type": random_route["type"],
    #             "required_signatures": random_route["quote"]["requiredSignatures"],
    #         }
    #         bebop_data["min_amounts_out"] = [
    #             int(to_sign_data["witness"]["maker_amount"])
    #         ]

    #         min_amounts_out = bebop_data["min_amounts_out"]
    #         data_to_sign = bebop_data["data_to_sign"]
    #         quote_id = bebop_data["quote_id"]
    #         route_type = bebop_data["route_type"]
    #         required_signatures = bebop_data["required_signatures"]

    #         # Get the deadline from the API
    #         deadline = int(to_sign_data["deadline"])

    #         # Set up the typed data for signing
    #         # Use the actual data from the API response
    #         single_pmmv3_typed_data = {
    #             "types": {
    #                 "EIP712Domain": [
    #                     {"name": "name", "type": "string"},
    #                     {"name": "version", "type": "string"},
    #                     {"name": "chainId", "type": "uint256"},
    #                     {"name": "verifyingContract", "type": "address"},
    #                 ],
    #                 "SingleOrder": [
    #                     {"name": "partner_id", "type": "uint64"},
    #                     {"name": "expiry", "type": "uint256"},
    #                     {"name": "taker_address", "type": "address"},
    #                     {"name": "maker_address", "type": "address"},
    #                     {"name": "maker_nonce", "type": "uint256"},
    #                     {"name": "taker_token", "type": "address"},
    #                     {"name": "maker_token", "type": "address"},
    #                     {"name": "taker_amount", "type": "uint256"},
    #                     {"name": "maker_amount", "type": "uint256"},
    #                     {"name": "receiver", "type": "address"},
    #                     {"name": "packed_commands", "type": "uint256"},
    #                 ],
    #             },
    #             "primaryType": "SingleOrder",
    #             "domain": {
    #                 "name": "BebopSettlement",
    #                 "version": "2",
    #                 "chainId": "6342",
    #                 "verifyingContract": "0xbbbbbBB520d69a9775E85b458C58c648259FAD5F",
    #             },
    #             "message": to_sign_data["witness"],  # Use witness directly from API
    #         }
    #         typed_data = single_pmmv3_typed_data

    #         text_encoded = encode_typed_data(full_message=typed_data)
    #         sign_data = self.web3.web3.eth.account.sign_message(
    #             text_encoded, private_key=self.private_key
    #         )

    #         order_data = {
    #             "min_amounts_out": min_amounts_out,
    #             "order_signature": self.web3.web3.to_hex(sign_data.signature),
    #             "quote_id": quote_id,
    #             "route_type": route_type,
    #             "required_signatures": required_signatures,
    #             "to_sign_data": to_sign_data,  # Include the full to_sign_data
    #         }

    #         await self._send_order(order_data)

    #     except Exception as e:
    #         import traceback

    #         input(traceback.format_exc())
    #         logger.error(f"{self.account_index} | Error swapping cUSD to WETH: {e}")
    #         return False

    # @retry_async(default_value=False)
    # async def _get_quote_data(
    #     self,
    #     partner_id,
    #     buy_tokens,
    #     sell_tokens,
    #     taker_address,
    #     gasless="true",
    #     receiver_address=None,
    #     source="bebop.xyz",
    #     approval_type="Permit2",
    #     sell_amounts=None,
    # ):
    #     try:
    #         headers = {
    #             "accept": "*/*",
    #             "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
    #             "origin": "https://bebop.xyz",
    #             "priority": "u=1, i",
    #             "referer": "https://bebop.xyz/",
    #             "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    #             "sec-ch-ua-mobile": "?0",
    #             "sec-ch-ua-platform": '"Windows"',
    #             "sec-fetch-dest": "empty",
    #             "sec-fetch-mode": "cors",
    #             "sec-fetch-site": "same-site",
    #             "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    #         }

    #         params = {
    #             "partner_id": partner_id,
    #             "buy_tokens": buy_tokens,
    #             "sell_tokens": sell_tokens,
    #             "taker_address": taker_address,
    #             "gasless": gasless,
    #             "receiver_address": receiver_address,
    #             "source": source,
    #             "approval_type": approval_type,
    #             "sell_amounts": sell_amounts,
    #         }

    #         curl_session = AsyncSession(
    #             impersonate="chrome131",
    #             proxies={
    #                 "http": f"http://{self.proxy}",
    #                 "https": f"http://{self.proxy}",
    #             },
    #             verify=False,
    #         )

    #         for _ in range(10):
    #             response = await curl_session.get(
    #                 "https://api.bebop.xyz/router/megaethtestnet/v1/quote",
    #                 params=params,
    #                 headers=headers,
    #             )
    #             if "TimedOut: TimedOut" in response.text:
    #                 logger.error(
    #                     f"{self.account_index} | Timed out, retrying... {_ + 1}/10"
    #                 )
    #                 await asyncio.sleep(1)
    #                 continue
    #             else:
    #                 break

    #         if response.status_code != 200:
    #             raise Exception(
    #                 f"Received response with status code: {response.status_code}"
    #             )

    #         return response.json()

    #     except Exception as e:
    #         logger.error(f"{self.account_index} | Error getting quote data Bebop: {e}")
    #         raise

    # @retry_async(default_value=False)
    # async def _send_order(self, order_data: dict):
    #     try:
    #         order_signature = order_data["order_signature"]
    #         quote_id = order_data["quote_id"]
    #         route_type = order_data["route_type"]
    #         required_signatures = order_data["required_signatures"]
    #         min_amounts_out = order_data["min_amounts_out"][0]
    #         to_sign_data = order_data["to_sign_data"]

    #         # Base payload with the order signature
    #         payload = {
    #             "signature": order_signature,
    #             "quote_id": quote_id,
    #         }

    #         # If required signatures exist, create the permit2 signature
    #         if required_signatures:
    #             # Generate permit signature using the data from the API response
    #             permit_signature, approvals_deadline, nonces = (
    #                 await self.get_fee_permit_signature(
    #                     required_signatures=required_signatures,
    #                     route_type=route_type,
    #                     to_sign_data=to_sign_data,
    #                 )
    #             )

    #             # Add permit2 data to payload
    #             payload["permit2"] = {
    #                 "signature": permit_signature,
    #                 "approvals_deadline": approvals_deadline,
    #                 "token_addresses": required_signatures,
    #                 "token_nonces": nonces,
    #             }

    #         headers = {
    #             "accept": "*/*",
    #             "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
    #             "content-type": "application/json; charset=utf-8",
    #             "origin": "https://bebop.xyz",
    #             "priority": "u=1, i",
    #             "referer": "https://bebop.xyz/",
    #             "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
    #             "sec-ch-ua-mobile": "?0",
    #             "sec-ch-ua-platform": '"Windows"',
    #             "sec-fetch-dest": "empty",
    #             "sec-fetch-mode": "cors",
    #             "sec-fetch-site": "same-site",
    #             "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    #         }

    #         curl_session = AsyncSession(
    #             impersonate="chrome131",
    #             proxies={
    #                 "http": f"http://{self.proxy}",
    #                 "https": f"http://{self.proxy}",
    #             },
    #             verify=False,
    #         )

    #         # Print the full payload for debugging
    #         print(payload)

    #         url = "https://api.bebop.xyz/pmm/megaethtestnet/v3/order"
    #         response = await curl_session.post(
    #             url,
    #             headers=headers,
    #             json=payload,
    #         )

    #         response_text = response.text
    #         print(response_text)  # Print for debugging

    #         # Try to parse as JSON
    #         try:
    #             response_data = response.json()
    #         except:
    #             response_data = {"text": response_text}

    #         if response.status_code != 200:
    #             raise Exception(
    #                 f"Received response with status code: {response.status_code}, response: {response_text}"
    #             )

    #         # Check for error in response
    #         if (
    #             response_data
    #             and isinstance(response_data, dict)
    #             and response_data.get("error")
    #         ):
    #             raise Exception(f"API Error: {response_data['error']}")

    #         # Status checking
    #         url += "-status"
    #         params = {"quote_id": quote_id}

    #         # Initialize tx_hash
    #         tx_hash = None

    #         # Simplified polling for transaction status
    #         max_retries = 10
    #         for i in range(max_retries):
    #             status_response = await curl_session.get(url=url, params=params)
    #             try:
    #                 status_data = status_response.json()
    #                 print(f"Status check {i+1}: {status_data}")

    #                 if status_data.get("txHash"):
    #                     tx_hash = status_data["txHash"]
    #                     logger.success(
    #                         f"{self.account_index} | Order completed with TX: {tx_hash}"
    #                     )
    #                     break
    #             except Exception as e:
    #                 logger.error(
    #                     f"{self.account_index} | Error parsing status response: {e}"
    #                 )

    #             await asyncio.sleep(5)

    #         if tx_hash:
    #             logger.success(
    #                 f"{self.account_index} | Swap transaction hash: {tx_hash}"
    #             )
    #             return True
    #         else:
    #             logger.warning(
    #                 f"{self.account_index} | No transaction hash found after {max_retries} retries"
    #             )
    #             return False

    #     except Exception as e:
    #         logger.error(f"{self.account_index} | Error in Bebop swap: {e}")
    #         raise

    # async def get_fee_permit_signature(
    #     self, required_signatures: list, route_type: str, to_sign_data: dict
    # ):
    #     # Get the deadline from to_sign_data
    #     deadline = int(to_sign_data["deadline"])

    #     # Get the nonce from to_sign_data
    #     nonce = to_sign_data["nonce"]

    #     balance_manager_address = Web3.to_checksum_address(
    #         "0xfe96910cf84318d1b8a5e2a6962774711467c0be"
    #     )
    #     router_jam_address = Web3.to_checksum_address(
    #         "0xbEbEbEb035351f58602E0C1C8B59ECBfF5d5f47b"
    #     )
    #     router_pmmv3_address = Web3.to_checksum_address(
    #         "0xbbbbbBB520d69a9775E85b458C58c648259FAD5F"
    #     )
    #     spender_address = Web3.to_checksum_address(
    #         "0x000000000022D473030F116dDEE9F6B43aC78BA3"
    #     )

    #     # Match the spender from to_sign_data
    #     spender = Web3.to_checksum_address(to_sign_data["spender"])

    #     # Get the exact tokens, amount from to_sign_data
    #     token = to_sign_data["permitted"]["token"]
    #     amount = to_sign_data["permitted"]["amount"]

    #     permit2_contract = self.web3.web3.eth.contract(
    #         address=spender_address, abi=PERMIT2_ABI
    #     )

    #     # Create a message that matches the exact structure expected by Bebop
    #     message = {
    #         "details": [
    #             {
    #                 "token": token,
    #                 "amount": amount,
    #                 "expiration": deadline,
    #                 "nonce": 0,  # Use 0 as default nonce
    #             }
    #         ],
    #         "spender": spender,
    #         "sigDeadline": deadline,
    #     }

    #     typed_data = {
    #         "types": {
    #             "EIP712Domain": [
    #                 {"name": "name", "type": "string"},
    #                 {"name": "chainId", "type": "uint256"},
    #                 {"name": "verifyingContract", "type": "address"},
    #             ],
    #             "PermitBatch": [
    #                 {"name": "details", "type": "PermitDetails[]"},
    #                 {"name": "spender", "type": "address"},
    #                 {"name": "sigDeadline", "type": "uint256"},
    #             ],
    #             "PermitDetails": [
    #                 {"name": "token", "type": "address"},
    #                 {"name": "amount", "type": "uint160"},
    #                 {"name": "expiration", "type": "uint48"},
    #                 {"name": "nonce", "type": "uint48"},
    #             ],
    #         },
    #         "primaryType": "PermitBatch",
    #         "domain": {
    #             "name": "Permit2",
    #             "chainId": CHAIN_ID,
    #             "verifyingContract": spender_address,
    #         },
    #         "message": message,
    #     }

    #     text_encoded = encode_typed_data(full_message=typed_data)
    #     sing_data = self.web3.web3.eth.account.sign_message(
    #         text_encoded, private_key=self.private_key
    #     )

    #     # Return the signature, deadline and array of nonces
    #     return self.web3.web3.to_hex(sing_data.signature), deadline, [0]


# PERMIT2_ABI = [
#     {
#         "inputs": [{"internalType": "uint256", "name": "deadline", "type": "uint256"}],
#         "name": "AllowanceExpired",
#         "type": "error",
#     },
#     {"inputs": [], "name": "ExcessiveInvalidation", "type": "error"},
#     {
#         "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
#         "name": "InsufficientAllowance",
#         "type": "error",
#     },
#     {
#         "inputs": [{"internalType": "uint256", "name": "maxAmount", "type": "uint256"}],
#         "name": "InvalidAmount",
#         "type": "error",
#     },
#     {"inputs": [], "name": "InvalidContractSignature", "type": "error"},
#     {"inputs": [], "name": "InvalidNonce", "type": "error"},
#     {"inputs": [], "name": "InvalidSignature", "type": "error"},
#     {"inputs": [], "name": "InvalidSignatureLength", "type": "error"},
#     {"inputs": [], "name": "InvalidSigner", "type": "error"},
#     {"inputs": [], "name": "LengthMismatch", "type": "error"},
#     {
#         "inputs": [
#             {"internalType": "uint256", "name": "signatureDeadline", "type": "uint256"}
#         ],
#         "name": "SignatureExpired",
#         "type": "error",
#     },
#     {
#         "anonymous": False,
#         "inputs": [
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "owner",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "token",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "spender",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint160",
#                 "name": "amount",
#                 "type": "uint160",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint48",
#                 "name": "expiration",
#                 "type": "uint48",
#             },
#         ],
#         "name": "Approval",
#         "type": "event",
#     },
#     {
#         "anonymous": False,
#         "inputs": [
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "owner",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "address",
#                 "name": "token",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "address",
#                 "name": "spender",
#                 "type": "address",
#             },
#         ],
#         "name": "Lockdown",
#         "type": "event",
#     },
#     {
#         "anonymous": False,
#         "inputs": [
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "owner",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "token",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "spender",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint48",
#                 "name": "newNonce",
#                 "type": "uint48",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint48",
#                 "name": "oldNonce",
#                 "type": "uint48",
#             },
#         ],
#         "name": "NonceInvalidation",
#         "type": "event",
#     },
#     {
#         "anonymous": False,
#         "inputs": [
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "owner",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "token",
#                 "type": "address",
#             },
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "spender",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint160",
#                 "name": "amount",
#                 "type": "uint160",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint48",
#                 "name": "expiration",
#                 "type": "uint48",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint48",
#                 "name": "nonce",
#                 "type": "uint48",
#             },
#         ],
#         "name": "Permit",
#         "type": "event",
#     },
#     {
#         "anonymous": False,
#         "inputs": [
#             {
#                 "indexed": True,
#                 "internalType": "address",
#                 "name": "owner",
#                 "type": "address",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint256",
#                 "name": "word",
#                 "type": "uint256",
#             },
#             {
#                 "indexed": False,
#                 "internalType": "uint256",
#                 "name": "mask",
#                 "type": "uint256",
#             },
#         ],
#         "name": "UnorderedNonceInvalidation",
#         "type": "event",
#     },
#     {
#         "inputs": [],
#         "name": "DOMAIN_SEPARATOR",
#         "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
#         "stateMutability": "view",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "", "type": "address"},
#             {"internalType": "address", "name": "", "type": "address"},
#             {"internalType": "address", "name": "", "type": "address"},
#         ],
#         "name": "allowance",
#         "outputs": [
#             {"internalType": "uint160", "name": "amount", "type": "uint160"},
#             {"internalType": "uint48", "name": "expiration", "type": "uint48"},
#             {"internalType": "uint48", "name": "nonce", "type": "uint48"},
#         ],
#         "stateMutability": "view",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "token", "type": "address"},
#             {"internalType": "address", "name": "spender", "type": "address"},
#             {"internalType": "uint160", "name": "amount", "type": "uint160"},
#             {"internalType": "uint48", "name": "expiration", "type": "uint48"},
#         ],
#         "name": "approve",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "token", "type": "address"},
#             {"internalType": "address", "name": "spender", "type": "address"},
#             {"internalType": "uint48", "name": "newNonce", "type": "uint48"},
#         ],
#         "name": "invalidateNonces",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "uint256", "name": "wordPos", "type": "uint256"},
#             {"internalType": "uint256", "name": "mask", "type": "uint256"},
#         ],
#         "name": "invalidateUnorderedNonces",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {"internalType": "address", "name": "token", "type": "address"},
#                     {"internalType": "address", "name": "spender", "type": "address"},
#                 ],
#                 "internalType": "struct IAllowanceTransfer.TokenSpenderPair[]",
#                 "name": "approvals",
#                 "type": "tuple[]",
#             }
#         ],
#         "name": "lockdown",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "", "type": "address"},
#             {"internalType": "uint256", "name": "", "type": "uint256"},
#         ],
#         "name": "nonceBitmap",
#         "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
#         "stateMutability": "view",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint160",
#                                 "name": "amount",
#                                 "type": "uint160",
#                             },
#                             {
#                                 "internalType": "uint48",
#                                 "name": "expiration",
#                                 "type": "uint48",
#                             },
#                             {
#                                 "internalType": "uint48",
#                                 "name": "nonce",
#                                 "type": "uint48",
#                             },
#                         ],
#                         "internalType": "struct IAllowanceTransfer.PermitDetails[]",
#                         "name": "details",
#                         "type": "tuple[]",
#                     },
#                     {"internalType": "address", "name": "spender", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "sigDeadline",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct IAllowanceTransfer.PermitBatch",
#                 "name": "permitBatch",
#                 "type": "tuple",
#             },
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permit",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint160",
#                                 "name": "amount",
#                                 "type": "uint160",
#                             },
#                             {
#                                 "internalType": "uint48",
#                                 "name": "expiration",
#                                 "type": "uint48",
#                             },
#                             {
#                                 "internalType": "uint48",
#                                 "name": "nonce",
#                                 "type": "uint48",
#                             },
#                         ],
#                         "internalType": "struct IAllowanceTransfer.PermitDetails",
#                         "name": "details",
#                         "type": "tuple",
#                     },
#                     {"internalType": "address", "name": "spender", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "sigDeadline",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct IAllowanceTransfer.PermitSingle",
#                 "name": "permitSingle",
#                 "type": "tuple",
#             },
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permit",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint256",
#                                 "name": "amount",
#                                 "type": "uint256",
#                             },
#                         ],
#                         "internalType": "struct ISignatureTransfer.TokenPermissions",
#                         "name": "permitted",
#                         "type": "tuple",
#                     },
#                     {"internalType": "uint256", "name": "nonce", "type": "uint256"},
#                     {"internalType": "uint256", "name": "deadline", "type": "uint256"},
#                 ],
#                 "internalType": "struct ISignatureTransfer.PermitTransferFrom",
#                 "name": "permit",
#                 "type": "tuple",
#             },
#             {
#                 "components": [
#                     {"internalType": "address", "name": "to", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "requestedAmount",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct ISignatureTransfer.SignatureTransferDetails",
#                 "name": "transferDetails",
#                 "type": "tuple",
#             },
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permitTransferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint256",
#                                 "name": "amount",
#                                 "type": "uint256",
#                             },
#                         ],
#                         "internalType": "struct ISignatureTransfer.TokenPermissions[]",
#                         "name": "permitted",
#                         "type": "tuple[]",
#                     },
#                     {"internalType": "uint256", "name": "nonce", "type": "uint256"},
#                     {"internalType": "uint256", "name": "deadline", "type": "uint256"},
#                 ],
#                 "internalType": "struct ISignatureTransfer.PermitBatchTransferFrom",
#                 "name": "permit",
#                 "type": "tuple",
#             },
#             {
#                 "components": [
#                     {"internalType": "address", "name": "to", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "requestedAmount",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct ISignatureTransfer.SignatureTransferDetails[]",
#                 "name": "transferDetails",
#                 "type": "tuple[]",
#             },
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permitTransferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint256",
#                                 "name": "amount",
#                                 "type": "uint256",
#                             },
#                         ],
#                         "internalType": "struct ISignatureTransfer.TokenPermissions",
#                         "name": "permitted",
#                         "type": "tuple",
#                     },
#                     {"internalType": "uint256", "name": "nonce", "type": "uint256"},
#                     {"internalType": "uint256", "name": "deadline", "type": "uint256"},
#                 ],
#                 "internalType": "struct ISignatureTransfer.PermitTransferFrom",
#                 "name": "permit",
#                 "type": "tuple",
#             },
#             {
#                 "components": [
#                     {"internalType": "address", "name": "to", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "requestedAmount",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct ISignatureTransfer.SignatureTransferDetails",
#                 "name": "transferDetails",
#                 "type": "tuple",
#             },
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {"internalType": "bytes32", "name": "witness", "type": "bytes32"},
#             {"internalType": "string", "name": "witnessTypeString", "type": "string"},
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permitWitnessTransferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {
#                         "components": [
#                             {
#                                 "internalType": "address",
#                                 "name": "token",
#                                 "type": "address",
#                             },
#                             {
#                                 "internalType": "uint256",
#                                 "name": "amount",
#                                 "type": "uint256",
#                             },
#                         ],
#                         "internalType": "struct ISignatureTransfer.TokenPermissions[]",
#                         "name": "permitted",
#                         "type": "tuple[]",
#                     },
#                     {"internalType": "uint256", "name": "nonce", "type": "uint256"},
#                     {"internalType": "uint256", "name": "deadline", "type": "uint256"},
#                 ],
#                 "internalType": "struct ISignatureTransfer.PermitBatchTransferFrom",
#                 "name": "permit",
#                 "type": "tuple",
#             },
#             {
#                 "components": [
#                     {"internalType": "address", "name": "to", "type": "address"},
#                     {
#                         "internalType": "uint256",
#                         "name": "requestedAmount",
#                         "type": "uint256",
#                     },
#                 ],
#                 "internalType": "struct ISignatureTransfer.SignatureTransferDetails[]",
#                 "name": "transferDetails",
#                 "type": "tuple[]",
#             },
#             {"internalType": "address", "name": "owner", "type": "address"},
#             {"internalType": "bytes32", "name": "witness", "type": "bytes32"},
#             {"internalType": "string", "name": "witnessTypeString", "type": "string"},
#             {"internalType": "bytes", "name": "signature", "type": "bytes"},
#         ],
#         "name": "permitWitnessTransferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {
#                 "components": [
#                     {"internalType": "address", "name": "from", "type": "address"},
#                     {"internalType": "address", "name": "to", "type": "address"},
#                     {"internalType": "uint160", "name": "amount", "type": "uint160"},
#                     {"internalType": "address", "name": "token", "type": "address"},
#                 ],
#                 "internalType": "struct IAllowanceTransfer.AllowanceTransferDetails[]",
#                 "name": "transferDetails",
#                 "type": "tuple[]",
#             }
#         ],
#         "name": "transferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
#     {
#         "inputs": [
#             {"internalType": "address", "name": "from", "type": "address"},
#             {"internalType": "address", "name": "to", "type": "address"},
#             {"internalType": "uint160", "name": "amount", "type": "uint160"},
#             {"internalType": "address", "name": "token", "type": "address"},
#         ],
#         "name": "transferFrom",
#         "outputs": [],
#         "stateMutability": "nonpayable",
#         "type": "function",
#     },
# ]
