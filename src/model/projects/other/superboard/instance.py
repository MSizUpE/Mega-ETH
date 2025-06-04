import asyncio
import random
import hashlib
import time
import os
import urllib.parse
import json
import re
from datetime import datetime, timezone, timedelta
from eth_account import Account
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
from web3 import Web3
from src.utils.decorators import retry_async
from src.utils.config import Config
from eth_account.messages import encode_defunct


class SuperBoard:
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

        self.bearer_token: str | None = None
        self.networks = {}

    async def quests(self):
        try:
            if not await self._login():
                return False

            campaigns = [
                "megaeth-testnet-real-time-era",
                "mega-testnet-explore-gte",
                "mega-testnet-explore-bebop",
                "mega-testnet-explore-teko",
                "mega-testnet-explore-cap",
                "mega-testnet-explore-bronto",
                "mega-testnet-explore-awe-box",
                "meet-rariblefun-nft-marketplace-on-megaeth-testnet",
                ]

            for campaign in campaigns:
                campaign_data = await self._get_quests(campaign)

                if campaign_data is None:
                    continue

                await self._complete_campaign(campaign_data)

            return True
        except Exception as e:
            logger.error(
                f"{self.account_index} | Error processing SuperBoard quests: {e}"
            )
            return False

    @retry_async(default_value=False)
    async def _login(self):
        try:
            utc_time = datetime.now(timezone.utc)

            payload = {
                "domain": "superboard.xyz",
                "address": self.wallet.address,
                "statement": "Login to SuperBoard",
                "uri": "https://superboard.xyz",
                "version": "1",
                "chainId": 1,
                "nonce": str(random.randint(100000000000000000, 999999999999999999)),
                "issuedAt": utc_time.strftime("%Y-%m-%dT%H:%M:%S")
                + f".{utc_time.microsecond // 1000:03d}Z",
                "expirationTime": (utc_time + timedelta(hours=1)).strftime(
                    "%Y-%m-%dT%H:%M:%S.000Z"
                ),
            }

            message = (
                f"superboard.xyz wants you to sign in with your Ethereum account:\n"
                f"{self.wallet.address}\n\n"
                f"Login to SuperBoard\n\n"
                f"URI: {payload['uri']}\n"
                f"Version: {payload['version']}\n"
                f"Chain ID: {payload['chainId']}\n"
                f"Nonce: {payload['nonce']}\n"
                f"Issued At: {payload['issuedAt']}\n"
                f"Expiration Time: {payload['expirationTime']}"
            )

            signature = "0x" + self._get_signature(message)

            json_data = {
                "0": {
                    "data": {
                        "header": {"t": "eip191"},
                        "payload": payload,
                        "signature": signature,
                    },
                    "networkId": 1,
                    "network": "ETHEREUM",
                    "family": "ETHEREUM",
                }
            }

            params = {
                "batch": "1",
            }

            headers = {
                "accept": "*/*",
                "authorization": "Bearer undefined",
                "content-type": "application/json",
                "origin": "https://superboard.xyz",
            }

            response = await self.session.post(
                "https://api-prod.superboard.xyz/api/trpc/auth.login",
                params=params,
                headers=headers,
                json=json_data,
            )

            if "User not found" in str(response.text):
                if not await self._register(payload, signature):
                    raise Exception("Failed to register")
                else:
                    return await self._login()
            
            if response.status_code < 200 or response.status_code > 299:
                raise Exception(response.text)

            response_data = response.json()
            self.bearer_token = response_data[0]["result"]["data"]["token"]

            # Store network IDs
            for network in response_data[0]["result"]["data"]["wallets"][0][
                "userNetworks"
            ]:
                self.networks[network["networkId"]] = network["id"]

            logger.success(
                f"{self.account_index} | Successfully logged in to SuperBoard"
            )
            return True

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error logging in to SuperBoard: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
    
    async def _register(self, payload, signature):
        try:
            headers = {
                'accept': '*/*',
                'authorization': 'Bearer undefined',
                'content-type': 'application/json',
                'origin': 'https://superboard.xyz',
            }

            params = {
                'batch': '1',
            }

            json_data = {
                '0': {
                    'wallets': [
                        {
                            'walledId': 10,
                            'walletName': 'Rabby',
                            'description': '',
                            'networks': [
                                {
                                    'networkId': 1,
                                    'address': self.wallet.address,
                                    'family': 'ETHEREUM',
                                    'verify': {
                                        'header': {
                                            't': 'eip191',
                                        },
                                        'payload': payload,
                                        'signature': signature,
                                    },
                                },
                            ],
                        },
                    ],
                    'uiProperties': {
                        'avatar': '',
                        'headerImage': '',
                        'language': 'ENGLISH',
                    },
                },
            }

            response = await self.session.post('https://api-prod.superboard.xyz/api/trpc/user.register', params=params, headers=headers, json=json_data)
            
            if response.status_code < 200 or response.status_code > 299:
                raise Exception(response.text)

            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Error registering: {e}")
            return False

    @retry_async(default_value=None)
    async def _get_quests(self, campaign_slug: str):
        try:
            headers = {
                "accept": "*/*",
                "authorization": f"Bearer {self.bearer_token}",
                "content-type": "application/json",
                "origin": "https://superboard.xyz",
            }

            params = {
                "batch": "1",
                "input": '{"0":{"slug":"' + campaign_slug + '"},"1":{}}',
            }

            response = await self.session.get(
                "https://api-prod.superboard.xyz/api/trpc/quest.getQuestBySlug,treat.getUserTreat",
                params=params,
                headers=headers,
            )

            if response.status_code < 200 or response.status_code > 299:
                raise Exception(response.text)

            data = response.json()[0]["result"]["data"]

            return data

        except Exception as e:
            logger.error(f"{self.account_index} | Error getting quests: {e}")
            raise e

    async def call(self, method, url, json=None, params=None):
        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {self.bearer_token}",
            "content-type": "application/json",
            "origin": "https://superboard.xyz",
        }

        if method == "GET":
            response = await self.session.get(url, params=params, headers=headers)
        elif method == "POST":
            response = await self.session.post(
                url, json=json, params=params, headers=headers
            )
        else:
            raise ValueError(f"Unsupported method: {method}")

        if response.status_code < 200 or response.status_code > 299:
            raise Exception(response.text)

        return response.json()

    @retry_async(default_value=False)
    async def _complete_campaign(self, campaign_data: dict):
        try:
            quest = campaign_data
            slug_input = urllib.parse.quote(
                json.dumps({"0": {"slug": quest["slug"]}}, separators=(",", ":"))
            )

            if "userQuest" not in campaign_data:
                quest_info = await self.call(
                    "POST",
                    f"https://api-prod.superboard.xyz/api/trpc/quest.userTakeQuest?batch=1",
                    json={"0": {"id": quest["id"], "userNetworkId": self.networks[1]}},
                )
                quest_info = (
                    await self.call(
                        "GET",
                        f"https://api-prod.superboard.xyz/api/trpc/quest.getQuestBySlug?batch=1&input={slug_input}",
                    )
                )[0]["result"]["data"]
            else:
                quest_info = campaign_data

            if "userQuest" not in quest_info:
                logger.warning(
                    f"{self.account_index} | {quest['name']} - Failed to start quest"
                )
                raise Exception(
                    f"{quest['name']} - Failed to start quest"
                )

            user_quest = quest_info["userQuest"][0]
            tasks_taken = [task["taskId"] for task in user_quest["tasksTaken"]]

            # Complete tasks
            completed = False
            for task in quest_info["tasks"]:
                if task["id"] in tasks_taken:
                    continue

                logger.info(f"{self.account_index} | Completing task {task['name']}")

                retry_count = 0
                max_retries = 3
                task_completed = False

                while retry_count < max_retries and not task_completed:
                    try:
                        verify_task = (
                            await self.call(
                                "POST",
                                "https://api-prod.superboard.xyz/api/trpc/task.userVerifyTask?batch=1",
                                json={
                                    "0": {
                                        "id": task["id"],
                                        "userQuestId": user_quest["id"],
                                        "userNetworkId": self.networks[
                                            task["networkId"]
                                        ],
                                        "answer": {
                                            "userQuestId": user_quest["id"],
                                            "userNetworkId": self.networks[
                                                task["networkId"]
                                            ],
                                            "id": task["id"],
                                        },
                                    }
                                },
                            )
                        )[0]

                        if "error" in verify_task:
                            retry_count += 1
                            logger.warning(
                                f"{self.account_index} | {task['name']} {verify_task['error']['message']} - Attempt {retry_count}/{max_retries}"
                            )
                            if retry_count < max_retries:
                                await asyncio.sleep(random.randint(3, 5))
                            else:
                                raise Exception(
                                    f"{self.account_index} | {task['name']} - Failed after {max_retries} attempts"
                                )
                        else:
                            logger.success(
                                f"{self.account_index} | {task['name']} - Task completed"
                            )
                            # Sleep between tasks
                            await asyncio.sleep(random.randint(3, 8))
                            completed = True
                            task_completed = True
                    except Exception as e:
                        retry_count += 1
                        logger.warning(
                            f"{self.account_index} | {task['name']} - Error: {str(e)} - Attempt {retry_count}/{max_retries}"
                        )
                        if retry_count < max_retries:
                            await asyncio.sleep(random.randint(3, 5))
                        else:
                            raise Exception(
                                f"{task['name']} - Failed after {max_retries} attempts"
                            )
                            

            # Verify quest completion
            data_input = urllib.parse.quote(
                json.dumps({"0": {"id": user_quest["questId"]}}, separators=(",", ":"))
            )
            verify_quest = (
                await self.call(
                    "GET",
                    f"https://api-prod.superboard.xyz/api/trpc/quest.verifyUserQuestCompletion?batch=1&input={data_input}",
                )
            )[0]

            if "error" in verify_quest:
                logger.warning(
                    f"{self.account_index} | {quest['name']} - Error during quest verification: {verify_quest['error']['message']}"
                )
            elif verify_quest["result"]["data"]["status"] == "success":
                logger.success(
                    f"{self.account_index} | {quest['name']} - Quest completed"
                )
            else:
                logger.warning(
                    f"{self.account_index} | {quest['name']} - {verify_quest}"
                )

            # Claim rewards
            claim_quest = (
                await self.call(
                    "POST",
                    "https://api-prod.superboard.xyz/api/trpc/quest.userQuestClaimRewards?batch=1",
                    json={
                        "0": {"type": "Points", "questId": str(user_quest["questId"])}
                    },
                )
            )[0]

            if "error" in claim_quest:
                if claim_quest["error"]["message"] == "User already claimed the reward":
                    logger.info(
                        f"{self.account_index} | {quest['name']} - Reward already claimed"
                    )
                else:
                    logger.warning(
                        f"{self.account_index} | {quest['name']} - Error claiming reward: {claim_quest['error']['message']}"
                    )
            elif claim_quest["result"]["data"]["status"] == "success":
                logger.success(
                    f"{self.account_index} | {quest['name']} - Reward received +{quest['rewardPoints']} Points"
                )
                return True

            return completed

        except Exception as e:
            if "User already claimed the reward" in str(e):
                logger.info(
                    f"{self.account_index} | {quest['name']} - Reward already claimed"
                )
                return True
            else:
                logger.error(f"{self.account_index} | Error completing campaign: {e}")
                return False

    @retry_async(default_value=None)
    async def _get_campaigns(self):
        try:
            response = await self.call(
                "GET", "https://api-prod.superboard.xyz/api/campaigns"
            )
            return response
        except Exception as e:
            logger.error(f"{self.account_index} | Error getting campaigns: {e}")
            raise e

    def _get_signature(self, message: str):
        encoded_msg = encode_defunct(text=message)
        signed_msg = Web3().eth.account.sign_message(
            encoded_msg, private_key=self.private_key
        )
        signature = signed_msg.signature.hex()
        return signature
