from decimal import Decimal
from typing import Dict, Optional, Union
from loguru import logger
from web3 import AsyncWeb3
from eth_account.signers.local import LocalAccount
from src.utils.decorators import retry_async
from src.model.onchain.constants import Balance
import asyncio
import traceback


class Web3Custom:
    def __init__(
        self,
        account_index: int,
        RPC_URLS: list[str],
        use_proxy: bool,
        proxy: str,
        ssl: bool = False,
    ):
        self.account_index = account_index
        self.RPC_URLS = RPC_URLS
        self.use_proxy = use_proxy
        self.proxy = proxy
        self.ssl = ssl
        self.web3 = None

    async def connect_web3(self) -> None:
        """
        Try to connect to each RPC URL in the list.
        Makes 3 attempts for each RPC with 1 second delay between attempts.
        """
        for rpc_url in self.RPC_URLS:
            for attempt in range(3):
                try:
                    proxy_settings = (
                        (f"http://{self.proxy}")
                        if (self.use_proxy and self.proxy)
                        else None
                    )
                    self.web3 = AsyncWeb3(
                        AsyncWeb3.AsyncHTTPProvider(
                            rpc_url,
                            request_kwargs={
                                "proxy": proxy_settings,
                                "ssl": self.ssl,
                            },
                        )
                    )

                    # Test connection
                    await self.web3.eth.chain_id
                    return

                except Exception as e:
                    logger.warning(
                        f"{self.account_index} | Attempt {attempt + 1}/3 failed for {rpc_url}: {str(e)}"
                    )
                    if attempt < 2:  # Don't sleep after the last attempt
                        await asyncio.sleep(1)
                    continue

        raise Exception("Failed to connect to any RPC URL")

    @retry_async(attempts=3, delay=3.0, default_value=None)
    async def get_balance(self, address: str) -> Balance:
        """
        Get balance of an address.

        Returns:
            Balance object with wei, gwei and ether values
        """
        wei_balance = await self.web3.eth.get_balance(address)
        return Balance.from_wei(wei_balance)

    @retry_async(attempts=3, delay=5.0, default_value=None)
    async def get_token_balance(
        self,
        wallet_address: str,
        token_address: str,
        token_abi: list = None,
        decimals: int = 18,
        symbol: str = "TOKEN",
    ) -> Balance:
        """
        Get token balance for any ERC20 token.

        Args:
            wallet_address: Address to check balance for
            token_address: Token contract address
            token_abi: Token ABI (optional)
            decimals: Token decimals (default is 18 for most ERC20 tokens)
            symbol: Token symbol (optional)

        Returns:
            Balance object with token balance
        """
        if token_abi is None:
            # Use minimal ERC20 ABI if none provided
            token_abi = [
                {
                    "constant": True,
                    "inputs": [{"name": "_owner", "type": "address"}],
                    "name": "balanceOf",
                    "outputs": [{"name": "balance", "type": "uint256"}],
                    "type": "function",
                }
            ]

        token_contract = self.web3.eth.contract(
            address=self.web3.to_checksum_address(token_address), abi=token_abi
        )
        wei_balance = await token_contract.functions.balanceOf(wallet_address).call()

        return Balance.from_wei(wei_balance, decimals=decimals, symbol=symbol)

    @retry_async(attempts=3, delay=5.0, default_value=None)
    async def get_gas_params(self) -> Dict[str, int]:
        try:
            gas_price = await self.web3.eth.gas_price
            return {"gasPrice": int(gas_price * 1.5)}
        except Exception as e:
            logger.error(
                f"{self.account_index} | Failed to get gas parameters: {str(e)}"
            )
            raise

    def convert_to_wei(self, amount: float, decimals: int) -> int:
        """Convert amount to wei based on token decimals."""
        return int(Decimal(str(amount)) * Decimal(str(10**decimals)))

    def convert_from_wei(self, amount: int, decimals: int) -> float:
        """Convert wei amount back to token units."""
        return float(Decimal(str(amount)) / Decimal(str(10**decimals)))

    @retry_async(attempts=1, delay=5.0, backoff=2.0, default_value=None)
    async def execute_transaction(
        self,
        tx_data: Dict,
        wallet: LocalAccount,
        chain_id: int,
        explorer_url: Optional[str] = None,
    ) -> str:
        """
        Execute a transaction and wait for confirmation.

        Args:
            tx_data: Transaction data
            wallet: Wallet instance (eth_account.LocalAccount)
            chain_id: Chain ID for the transaction
            explorer_url: Explorer URL for logging (optional)
        """
        try:
            nonce = await self.web3.eth.get_transaction_count(wallet.address)
            gas_params = await self.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            transaction = {
                "from": wallet.address,
                "nonce": nonce,
                "chainId": chain_id,
                **tx_data,
                **gas_params,
            }

            # Add type 2 only for EIP-1559 transactions
            if "maxFeePerGas" in gas_params:
                transaction["type"] = 2

            signed_txn = self.web3.eth.account.sign_transaction(transaction, wallet.key)
            tx_hash = await self.web3.eth.send_raw_transaction(
                signed_txn.raw_transaction
            )

            logger.info(
                f"{self.account_index} | Waiting for transaction confirmation..."
            )
            receipt = await self.web3.eth.wait_for_transaction_receipt(
                tx_hash, poll_latency=2
            )

            if receipt["status"] == 1:
                tx_hex = tx_hash.hex()
                success_msg = f"Transaction successful!"
                if explorer_url:
                    success_msg += f" Explorer URL: {explorer_url}{tx_hex}"
                logger.success(success_msg)
                return tx_hex
            else:
                raise Exception("Transaction failed")
        except Exception as e:
            logger.error(
                f"{self.account_index} | Transaction execution failed: {str(e)}"
            )
            raise

    @retry_async(attempts=3, delay=5.0, backoff=2.0, default_value=None)
    async def approve_token(
        self,
        token_address: str,
        spender_address: str,
        amount: int,
        wallet: LocalAccount,
        chain_id: int,
        token_abi: list = None,
        explorer_url: Optional[str] = None,
    ) -> Optional[str]:
        """
        Approve token spending for any contract.

        Args:
            token_address: Address of the token contract
            spender_address: Address of the contract to approve spending for
            amount: Amount to approve (in wei)
            wallet: Wallet instance (eth_account.LocalAccount)
            chain_id: Chain ID for the transaction
            token_abi: Token contract ABI (optional, will use minimal ABI if not provided)
            explorer_url: Explorer URL for logging (optional)
        """
        try:
            if token_abi is None:
                # Use minimal ERC20 ABI if none provided
                token_abi = [
                    {
                        "constant": True,
                        "inputs": [
                            {"name": "_owner", "type": "address"},
                            {"name": "_spender", "type": "address"},
                        ],
                        "name": "allowance",
                        "outputs": [{"name": "", "type": "uint256"}],
                        "type": "function",
                    },
                    {
                        "constant": False,
                        "inputs": [
                            {"name": "_spender", "type": "address"},
                            {"name": "_value", "type": "uint256"},
                        ],
                        "name": "approve",
                        "outputs": [{"name": "", "type": "bool"}],
                        "type": "function",
                    },
                ]

            token_contract = self.web3.eth.contract(
                address=self.web3.to_checksum_address(token_address), abi=token_abi
            )

            current_allowance = await token_contract.functions.allowance(
                wallet.address, spender_address
            ).call()

            if current_allowance >= amount:
                logger.info(
                    f"{self.account_index} | Allowance sufficient for token {token_address}"
                )
                return None

            gas_params = await self.get_gas_params()
            if gas_params is None:
                raise Exception("Failed to get gas parameters")

            approve_tx = await token_contract.functions.approve(
                spender_address, amount
            ).build_transaction(
                {
                    "from": wallet.address,
                    "nonce": await self.web3.eth.get_transaction_count(wallet.address),
                    "chainId": chain_id,
                    **gas_params,
                }
            )

            return await self.execute_transaction(
                approve_tx, wallet=wallet, chain_id=chain_id, explorer_url=explorer_url
            )

        except Exception as e:
            logger.error(
                f"{self.account_index} | Failed to approve token {token_address}: {str(e)}"
            )
            raise

    @retry_async(attempts=3, delay=5.0, default_value=None)
    async def wait_for_balance_increase(
        self,
        wallet_address: str,
        initial_balance: float,
        token_address: Optional[str] = None,
        token_abi: Optional[list] = None,
        timeout: int = 60,
        check_interval: int = 5,
        log_interval: int = 15,
        account_index: Optional[int] = None,
    ) -> bool:
        """
        Wait for balance to increase (works for both native coin and tokens).

        Args:
            wallet_address: Address to check balance for
            initial_balance: Initial balance to compare against
            token_address: Token address (if waiting for token balance)
            token_abi: Token ABI (optional, for tokens)
            timeout: Maximum time to wait in seconds
            check_interval: How often to check balance in seconds
            log_interval: How often to log progress in seconds
            account_index: Optional account index for logging
        """

        logger.info(
            f"{self.account_index} | Waiting for balance to increase (max wait time: {timeout} seconds)..."
        )
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Get current balance (either native coin or token)
            if token_address:
                current_balance = await self.get_token_balance(
                    wallet_address, token_address, token_abi
                )
            else:
                current_balance = await self.get_balance(wallet_address)

            if current_balance > initial_balance:
                logger.success(
                    f"{self.account_index} | Balance increased from {initial_balance} to {current_balance}"
                )
                return True

            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % log_interval == 0:
                logger.info(
                    f"{self.account_index} | Still waiting for balance to increase... ({elapsed}/{timeout} seconds)"
                )

            await asyncio.sleep(check_interval)

        logger.error(
            f"{self.account_index} | Balance didn't increase after {timeout} seconds"
        )
        return False

    @retry_async(attempts=3, delay=10.0, default_value=None)
    async def estimate_gas(self, transaction: dict) -> int:
        """Estimate gas for transaction and add some buffer."""
        try:
            estimated = await self.web3.eth.estimate_gas(transaction)
            # Adding 10% to estimated gas for safety
            return int(estimated * 2.2)
        except Exception as e:
            logger.warning(f"{self.account_index} | Error estimating gas: {e}.")
            raise e

    @classmethod
    async def create(
        cls,
        account_index: int,
        RPC_URLS: list[str],
        use_proxy: bool,
        proxy: str,
        ssl: bool = False,
    ) -> "Web3Custom":
        """
        Async factory method for creating a class instance.
        """
        instance = cls(account_index, RPC_URLS, use_proxy, proxy, ssl)
        await instance.connect_web3()
        return instance

    async def cleanup(self):
        try:
            """
            Cleanup method to properly close the Web3 client session.
            Should be called when done using the Web3 instance.
            """
            if not self.web3:
                logger.warning(
                    f"{self.account_index} | No web3 instance found during cleanup"
                )
                return

            if hasattr(self.web3, "provider"):
                provider = self.web3.provider

                # Disconnect the provider
                if hasattr(provider, "disconnect"):
                    await provider.disconnect()
                    logger.info(
                        f"{self.account_index} | Web3 provider disconnected successfully"
                    )

                # Additionally try to close any session that might exist
                if hasattr(provider, "_request_kwargs") and isinstance(
                    provider._request_kwargs, dict
                ):
                    session = provider._request_kwargs.get("session")
                    if session and hasattr(session, "close") and not session.closed:
                        await session.close()
                        logger.info(
                            f"{self.account_index} | Additional session cleanup completed"
                        )
            else:
                logger.warning(
                    f"{self.account_index} | No provider found in web3 instance"
                )

        except Exception as e:
            logger.error(
                f"{self.account_index} | Error cleaning up Web3 client: {str(e)}\nTraceback: {traceback.format_exc()}"
            )

    def encode_function_call(self, function_name: str, params: dict, abi: list) -> str:
        """
        Encode function call data using contract ABI.

        Args:
            function_name: Name of the function to call
            params: Parameters for the function
            abi: Contract ABI
        """
        contract = self.web3.eth.contract(abi=abi)
        return contract.encodeABI(fn_name=function_name, args=[params])

    async def send_transaction(
        self,
        to: str,
        data: str,
        wallet: LocalAccount,
        value: int = 0,
        chain_id: Optional[int] = None,
    ) -> str:
        """
        Send a transaction with encoded data.

        Args:
            to: Contract address
            data: Encoded function call data
            wallet: Wallet instance
            value: Amount of native tokens to send
            chain_id: Chain ID (optional)
        """
        if chain_id is None:
            chain_id = await self.web3.eth.chain_id

        # Get gas estimate
        tx_params = {
            "from": wallet.address,
            "to": to,
            "data": data,
            "value": value,
            "chainId": chain_id,
        }

        try:
            gas_limit = await self.estimate_gas(tx_params)
            tx_params["gas"] = gas_limit
        except Exception as e:
            raise e

        # Get gas price params
        gas_params = await self.get_gas_params()
        tx_params.update(gas_params)

        # Get nonce
        tx_params["nonce"] = await self.web3.eth.get_transaction_count(wallet.address)

        # Sign and send transaction
        signed_tx = self.web3.eth.account.sign_transaction(tx_params, wallet.key)
        tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)

        return tx_hash.hex()
