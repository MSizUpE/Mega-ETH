import asyncio
import json
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

# Define the ABI for the mint function
RARIBLE_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"},
            {"internalType": "uint256", "name": "param2", "type": "uint256"},
            {"internalType": "address", "name": "param3", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
            {
                "internalType": "tuple",
                "name": "param5",
                "type": "tuple",
                "components": [
                    {"internalType": "address", "name": "param1", "type": "address"},
                    {"internalType": "uint256", "name": "param2", "type": "uint256"},
                    {"internalType": "uint256", "name": "param3", "type": "uint256"},
                    {"internalType": "address", "name": "param4", "type": "address"},
                ],
            },
            {"internalType": "bytes", "name": "param6", "type": "bytes"},
        ],
        "name": "claim",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class Rarible:
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
            if len(self.config.MINTS.RARIBLE.CONTRACTS_TO_BUY) > 0:
                random_token_contract = random.choice(
                    self.config.MINTS.RARIBLE.CONTRACTS_TO_BUY
                )
                random_token_contract = await self._get_contract_data(
                    random_token_contract
                )
                if not random_token_contract:
                    logger.error(f"{self.account_index} | Failed to get contract data")
                    return False
            else:
                logger.error(
                    f"{self.account_index} | No contract to buy from config for Rarible. Exiting..."
                )
                return False
                random_token_contract = await self._get_random_token_for_mint()
                if not random_token_contract:
                    logger.error(
                        f"{self.account_index} | Failed to get random token for mint"
                    )
                    return False

            return await self._mint(random_token_contract)
        except Exception as e:
            logger.error(f"{self.account_index} | Failed to buy meme on Rarible: {e}")
            return False

    @retry_async(default_value=False)
    async def _mint(self, token_data: dict):
        try:
            # Contract address for minting
            contract_address = Web3.to_checksum_address(token_data["contract_address"])

            # Get wallet address
            wallet_address = self.wallet.address
            wallet_address_no_prefix = wallet_address[2:].lower()

            # Token price in wei
            price_in_wei = Web3.to_wei(token_data["price"], "ether")

            # Instead of using contract.functions, directly use the function selector and encoded parameters
            # This is the claim function selector with the necessary parameters
            # Using the example payload provided but replacing the address with the current wallet
            payload = (
                "0x84bb1e42"
                + "000000000000000000000000"
                + wallet_address_no_prefix
                + "0000000000000000000000000000000000000000000000000000000000000001000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
                + price_in_wei.to_bytes(32, byteorder="big").hex()
                + "00000000000000000000000000000000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000016000000000000000000000000000000000000000000000000000000000000000800000000000000000000000000000000000000000000000000000000000000000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000"
            )

            # Prepare basic transaction similar to cap_app.py
            tx = {
                "from": wallet_address,
                "to": contract_address,
                "data": payload,
                "value": price_in_wei,
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
            tx["nonce"] = await self.web3.web3.eth.get_transaction_count(wallet_address)

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
                    f"{self.account_index} | NFT minted successfully! TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return True
            else:
                raise Exception(f"Transaction failed. Status: {receipt['status']}")

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error minting NFT: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    @retry_async(default_value=None)
    async def _get_random_token_for_mint(self) -> dict:
        """
        Contract example:
        {
            "id":"MEGAETHTESTNET:0xe03ec91569dbab90a3a632dbbf38ea8a768fc0e1",
            "title":"Floating",
            "media":{
                "type":"image",
                "url":"/images/drops/floating/drop-preview.webp"
            },
            "description":"I find myself floating, waiting for what is next, hoping that the water carries me away.",
            "startDate":"2025-05-02T14:00:00Z",
            "endDate":"2025-05-09T14:00:00Z",
            "price":{
                "amount":"0.004",
                "currency":{
                    "id":"MEGAETH:0x0000000000000000000000000000000000000000",
                    "abbreviation":"eth",
                    "usdExchangeRate":"1838.2691252228587",
                    "icon":"/images/currencies/ethereum.svg"
                }
            },
            "quantity":"None",
            "blockchain":"MEGAETHTESTNET",
            "isVerified":true,
            "maxMintPerWallet":"None",
            "author":"Sherie Margaret Ngigi",
            "tokenStandard":"ERC721",
            "background":"/images/drops/floating/cover.webp",
            "preview":"/images/drops/floating/preview.webp",
            "previewType":"image"
        },
        """
        try:
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "ru,en-US;q=0.9,en;q=0.8,ru-RU;q=0.7,zh-TW;q=0.6,zh;q=0.5,uk;q=0.4",
                "cache-control": "max-age=0",
                "priority": "u=0, i",
                "referer": "https://testnet.rarible.fun/drops",
                "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            }

            response = await self.session.get(
                "https://testnet.rarible.fun/drops", headers=headers
            )

            html_content = response.text

            json_data = html_content.split('__next_f.push([1,"4:')[1].split('\\n"')[0]
            # Fix escaped JSON string and parse it properly
            json_data = json_data.replace('\\"', '"').replace("\\\\", "\\")
            parsed_data = json.loads(json_data)

            # Extract contract addresses from the parsed data
            contracts = []
            for item in parsed_data:
                contracts.append(
                    {
                        "contract_address": item["id"].split(":")[1],
                        "ticker": item["title"],
                        "price": float(item["price"]["amount"]),
                    }
                )

            random_contract = random.choice(contracts)

            logger.info(
                f"{self.account_index} | Will try to mint token {random_contract['ticker']} | {random_contract['contract_address']} "
            )
            return random_contract

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error getting random token for mint: {str(e)}"
            )
            raise e

    @retry_async(default_value=None)
    async def _get_contract_data(self, contract_address: str) -> dict:
        try:
            headers = {
                "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "accept-language": "ru,en-US;q=0.9,en;q=0.8,ru-RU;q=0.7,zh-TW;q=0.6,zh;q=0.5,uk;q=0.4",
                "cache-control": "max-age=0",
                "priority": "u=0, i",
                "referer": "https://testnet.rarible.fun/drops",
                "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "document",
                "sec-fetch-mode": "navigate",
                "sec-fetch-site": "same-origin",
                "sec-fetch-user": "?1",
                "upgrade-insecure-requests": "1",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            }

            response = await self.session.get(
                f"https://testnet.rarible.fun/collections/megaethtestnet/{contract_address}/drops",
                headers=headers,
            )

            html_content = response.text

            quote = '{\\"id\\":\\"MEGAETHTESTNET:' + contract_address + '\\",'

            json_data = quote + html_content.split(quote)[1].split('\\n"')[0]
            # Fix escaped JSON string and parse it properly
            json_data = json_data.replace('\\"', '"').replace("\\\\", "\\")
            parsed_data = json.loads(json_data)

            return {
                "contract_address": parsed_data["id"].split(":")[1],
                "ticker": parsed_data["title"],
                "price": float(parsed_data["price"]["amount"]),
            }

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error getting random token for mint: {str(e)}"
            )
            raise e
