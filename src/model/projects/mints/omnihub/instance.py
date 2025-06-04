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

# ERC721 ABI for NFT balance check
ERC721_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]


class OmniHub:
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
    async def mint(self):
        try:
            max_price_to_mint = self.config.MINTS.OMNIHUB.MAX_PRICE_TO_MINT

            contracts_to_mint = await self._get_random_token_for_mint(
                max_price_to_mint
            )

            if not contracts_to_mint:
                logger.error(
                    f"{self.account_index} | No contracts to mint found"
                )
                return False

            contract_to_mint = random.choice(contracts_to_mint)
    
            logger.info(
                f"{self.account_index} | Minting NFT from {contract_to_mint['title']} with price {contract_to_mint['price']}"
            )

            # Check current NFT balance before minting
            current_balance = await self._check_nft_balance(contract_to_mint['address'])
            logger.info(
                f"{self.account_index} | Current NFT balance for contract {contract_to_mint['address']}: {current_balance}"
            )

            # Mint the NFT
            mint_success = await self._mint_nft(contract_to_mint)

            return mint_success

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error minting OmniHub: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=0)
    async def _check_nft_balance(self, contract_address: str) -> int:
        """Check the NFT balance for the current wallet from the given contract."""
        try:
            nft_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(contract_address),
                abi=ERC721_ABI,
            )

            balance = await nft_contract.functions.balanceOf(self.wallet.address).call()
            return balance
        except Exception as e:
            logger.error(f"{self.account_index} | Error checking NFT balance: {e}")
            raise e

    @retry_async(default_value=False)
    async def _mint_nft(self, contract: dict):
        try:
            price = contract["price"]
            title = contract["title"]
            address = contract["address"]

            payload = "0xa0712d680000000000000000000000000000000000000000000000000000000000000001"

            tx_hash = await self.web3.send_transaction(
                to=address,
                data=payload,
                wallet=self.wallet,
                value=Web3.to_wei(price, "ether"),
                chain_id=CHAIN_ID,
            )

            # Wait for transaction receipt to confirm success
            logger.info(
                f"{self.account_index} | Waiting for transaction confirmation..."
            )
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(
                tx_hash, timeout=120
            )

            if receipt["status"] == 1:
                logger.success(
                    f"{self.account_index} | Successfully minted OmniHub NFT at {title}: {EXPLORER_URL_MEGAETH}{tx_hash}"
                )
                return True
            else:
                logger.error(
                    f"{self.account_index} | Transaction failed: {EXPLORER_URL_MEGAETH}{tx_hash}"
                )
                return False

        except Exception as e:
            raise e

    @retry_async(default_value=None)
    async def _get_random_token_for_mint(self, max_price: float) -> str:
        page = 1
        constracts = []

        while page < 6:
            for retry in range(3):
                try:
                    headers = {
                        'Accept': 'application/json',
                        'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5',
                        'Connection': 'keep-alive',
                        'Origin': 'https://omnihub.xyz',
                        'Referer': 'https://omnihub.xyz/',
                        'Sec-Fetch-Dest': 'empty',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'same-site',
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
                        'sec-ch-ua': '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                        'sec-ch-ua-mobile': '?0',
                        'sec-ch-ua-platform': '"Windows"',
                    }

                    params = {
                        'page': '1',
                        'chain': 'megaeth-testnet',
                        'sort_by': 'trending',
                        'search': '',
                        'time_interval': '30d',
                    }

                    response = await self.session.get('https://api.omnihub.xyz/api/contract/list', params=params, headers=headers)

                    data = response.json()["data"]
                    for contract in data:
                        price_eth = Web3.from_wei(int(contract["fee"]), "ether")
                        if price_eth <= max_price:
                            constracts.append(
                                {
                                "address": contract["address"],
                                "title": contract["title"],
                                "price": price_eth,
                            }
                        )

                    page += 1
                    break

                except Exception as e:
                    logger.error(
                        f"{self.account_index} | Error getting random token for mint: {str(e)}"
                    )
                    if retry == 2:
                        return constracts

        return constracts
