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

TIMER_PAYLOAD = "0x608060405260405161052438038061052483398181016040528101906100259190610188565b60003411610068576040517f08c379a000000000000000000000000000000000000000000000000000000000815260040161005f90610212565b60405180910390fd5b600034111561011f5760008173ffffffffffffffffffffffffffffffffffffffff163460405161009790610263565b60006040518083038185875af1925050503d80600081146100d4576040519150601f19603f3d011682016040523d82523d6000602084013e6100d9565b606091505b505090508061011d576040517f08c379a0000000000000000000000000000000000000000000000000000000008152600401610114906102c4565b60405180910390fd5b505b506102e4565b600080fd5b600073ffffffffffffffffffffffffffffffffffffffff82169050919050565b60006101558261012a565b9050919050565b6101658161014a565b811461017057600080fd5b50565b6000815190506101828161015c565b92915050565b60006020828403121561019e5761019d610125565b5b60006101ac84828501610173565b91505092915050565b600082825260208201905092915050565b7f4465706c6f796d656e7420726571756972657320612066656500000000000000600082015250565b60006101fc6019836101b5565b9150610207826101c6565b602082019050919050565b6000602082019050818103600083015261022b816101ef565b9050919050565b600081905092915050565b50565b600061024d600083610232565b91506102588261023d565b600082019050919050565b600061026e82610240565b9150819050919050565b7f466565207472616e73666572206661696c656400000000000000000000000000600082015250565b60006102ae6013836101b5565b91506102b982610278565b602082019050919050565b600060208201905081810360008301526102dd816102a1565b9050919050565b610231806102f36000396000f3fe608060405234801561001057600080fd5b50600436106100415760003560e01c80632baeceb714610046578063a87d942c14610050578063d09de08a1461006e575b600080fd5b61004e610078565b005b6100586100ca565b604051610065919061013e565b60405180910390f35b6100766100d3565b005b60008081548092919061008a90610188565b91905055507f1a00a27c962d5410357331e1a8cffff62058bd0161ad624818df31152f1eeb456000546040516100c0919061013e565b60405180910390a1565b60008054905090565b6000808154809291906100e5906101b2565b91905055507f3cf8b50771c17d723f2cb711ca7dadde485b222e13c84ba0730a14093fad6d5c60005460405161011b919061013e565b60405180910390a1565b6000819050919050565b61013881610125565b82525050565b6000602082019050610153600083018461012f565b92915050565b7f4e487b7100000000000000000000000000000000000000000000000000000000600052601160045260246000fd5b600061019382610125565b915060008214156101a7576101a6610159565b5b600182039050919050565b60006101bd82610125565b91507fffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff8214156101f0576101ef610159565b5b60018201905091905056fea2646970667358221220526250c31d8148ffcfa6d06ab24c6dfbf02441f204c5578890519ec2fdd071c564736f6c63430008090033000000000000000000000000fda77b68d08988e91932a3a4ff4d49d4771536f8"


class EasyNode:
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
    async def deploy_contract(self):
        try:
            # Prepare basic transaction
            tx = {
                "from": self.wallet.address,
                "to": "",  # Empty address for contract deployment
                "data": TIMER_PAYLOAD,
                "value": Web3.to_wei(0.00001, "ether"),
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
                contract_address = receipt["contractAddress"]
                logger.success(
                    f"{self.account_index} | Cpunter contract deployed successfully! Address: {contract_address} TX: {EXPLORER_URL_MEGAETH}{tx_hex}"
                )
                return contract_address
            else:
                raise Exception(f"Transaction failed. Status: {receipt['status']}")

        except Exception as e:
            random_pause = random.randint(
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1],
            )
            logger.error(
                f"{self.account_index} | Error deploying Counter contract: {e}. Waiting {random_pause} seconds..."
            )
            await asyncio.sleep(random_pause)
            raise
