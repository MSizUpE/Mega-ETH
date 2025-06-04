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


class Nerzo:
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

    @retry_async(default_value=False)
    async def mint_megaeth(self):
        try:
            # Prepare the wallet address without 0x prefix
            wallet_address_no_prefix = self.wallet.address[2:].lower()

            # Construct the payload with the wallet address inserted
            payload = f"0x84bb1e42000000000000000000000000{wallet_address_no_prefix}0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee0000000000000000000000000000000000000000000000000003328b944c400000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000016000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

            # Prepare basic transaction
            tx = {
                "from": self.wallet.address,
                "to": "0xb256434FA22F0D0D8fb9FEE6b685E88E8D498dA5",
                "data": payload,
                "value": Web3.to_wei(0.0009, "ether"),
            }

            # Estimate gas
            try:
                gas_limit = await self.web3.estimate_gas(tx)
                tx["gas"] = gas_limit
            except Exception as e:
                raise e

            # Get gas price parameters
            gas_params = await self.web3.get_gas_params()
            tx.update(gas_params)

            # Add chain ID and nonce
            tx["chainId"] = CHAIN_ID
            tx["nonce"] = await self.web3.web3.eth.get_transaction_count(
                self.wallet.address
            )

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
                    f"{self.account_index} | Nerzo MegaETH minted successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                raise Exception(
                    f"Transaction failed. Status: {receipt['status']}"
                )

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error minting Nerzo MegaETH: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=False)
    async def mint_fluffle(self):
        try:
            # Prepare the wallet address without 0x prefix
            wallet_address_no_prefix = self.wallet.address[2:].lower()

            # Construct the payload with the wallet address inserted
            payload = f"0x84bb1e42000000000000000000000000{wallet_address_no_prefix}0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee0000000000000000000000000000000000000000000000000001c6bf5263400000000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000016000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"

            # Prepare basic transaction
            tx = {
                "from": self.wallet.address,
                "to": "0x596712ff1cB42005f5f4e0534a939F98209cb46e",
                "data": payload,
                "value": Web3.to_wei(0.0005, "ether"),
            }

            # Estimate gas
            try:
                gas_limit = await self.web3.estimate_gas(tx)
                tx["gas"] = gas_limit
            except Exception as e:
                raise e

            # Get gas price parameters
            gas_params = await self.web3.get_gas_params()
            tx.update(gas_params)

            # Add chain ID and nonce
            tx["chainId"] = CHAIN_ID
            tx["nonce"] = await self.web3.web3.eth.get_transaction_count(
                self.wallet.address
            )

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
                    f"{self.account_index} | Nerzo Fluffle minted successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                raise Exception(
                    f"Transaction failed. Status: {receipt['status']}"
                )

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error minting Nerzo Fluffle: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
