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
from eth_account.messages import encode_defunct


class HopNetwork:
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

    @retry_async(default_value=False)
    async def waitlist(self):
        try:
            message = f"{self.wallet.address} agrees to join the hop waitlist. Signed on {int(time.time() * 1000)}"
            signature = "0x" + self._get_signature(message)

            bearer = await self._get_bearer()

            headers = {
                "accept": "*/*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8,ru;q=0.7,zh-TW;q=0.6,zh;q=0.5",
                "apikey": bearer,
                "authorization": f"Bearer {bearer}",
                "content-profile": "public",
                "content-type": "application/json",
                "origin": "https://hopnetwork.xyz",
                "prefer": "",
                "priority": "u=1, i",
                "referer": "https://hopnetwork.xyz/",
                "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "cross-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
                "x-client-info": "supabase-js-web/2.49.3",
            }

            json_data = {
                "wallet": self.wallet.address.lower(),
                "signature": signature,
            }

            response = await self.session.post(
                "https://laiazupevpbcmgwgjkuh.supabase.co/rest/v1/waitlist",
                headers=headers,
                json=json_data,
            )

            if "duplicate key value violates unique constraint" in response.text:
                logger.success(
                    f"{self.account_index} | Already in waitlist."
                )
                return True
            
            if response.status_code < 200 or response.status_code > 299:
                raise Exception(response.text)

            logger.success(
                f"{self.account_index} | Successfully joined waitlist on HopNetwork"
            )
            return True
        
        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error joining waitlist on HopNetwork: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise

    async def _get_bearer(self):
        headers = {
            "sec-ch-ua-platform": '"Windows"',
            "Referer": "https://hopnetwork.xyz/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "sec-ch-ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "sec-ch-ua-mobile": "?0",
        }

        params = {
            "dpl": "dpl_9Xtj6JGdZRCfse1Q7Mn5bLsYJXAA",
        }

        response = await self.session.get(
            "https://hopnetwork.xyz/_next/static/chunks/app/page-f1a419894b2c8b40.js",
            params=params,
            headers=headers,
        )
        bearer = response.text.split('"https://laiazupevpbcmgwgjkuh.supabase.co","')[
            1
        ].split('"')[0]
        return bearer

    def _get_signature(self, message: str):
        encoded_msg = encode_defunct(text=message)
        signed_msg = Web3().eth.account.sign_message(
            encoded_msg, private_key=self.private_key
        )
        signature = signed_msg.signature.hex()
        return signature
