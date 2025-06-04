import random
from eth_account.messages import encode_typed_data
from eth_account import Account
from src.model.projects.swaps.constants import GTE_SWAPS_ABI, GTE_SWAPS_CONTRACT, GTE_TOKENS
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
from web3 import Web3
from curl_cffi.requests import AsyncSession
import time
import asyncio

from src.utils.decorators import retry_async
from src.utils.config import Config
from src.utils.constants import EXPLORER_URL_MEGAETH, ERC20_ABI, BALANCE_CHECKER_ABI, BALANCE_CHECKER_CONTRACT_ADDRESS


class GteSwaps:
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
        self.contract = self.web3.web3.eth.contract(
            address=self.web3.web3.to_checksum_address(GTE_SWAPS_CONTRACT), 
            abi=GTE_SWAPS_ABI
        )

    @retry_async(default_value=([], None))
    async def _get_path(self, balances: dict) -> tuple[list[str], str]:
        try:
            # Get tokens with non-zero balance (excluding native ETH)
            tokens_with_balance = {token: balance for token, balance in balances.items() 
                                if token != "native" and balance > 0}
            
            # Path format: [from_token_address, to_token_address]
            path = []
            swap_type = ""
            
            # 50/50 chance to do native->token swap regardless of token balances
            do_native_swap = random.choice([True, False])
            
            # CASE 1: If no tokens have balance or we randomly chose to do a native swap
            if not tokens_with_balance or do_native_swap:
                logger.info(f"[{self.account_index}] Creating ETH -> token path" + 
                           (" (random choice)" if tokens_with_balance and do_native_swap else " (no token balances)"))
                
                # Choose a random token from GTE_TOKENS excluding WETH (to prevent ETH->WETH swaps)
                available_tokens = [token for token in GTE_TOKENS.keys() if token != "WETH"]
                target_token = random.choice(available_tokens)
                
                # Path: ETH (WETH address) -> random token
                weth_address = self.web3.web3.to_checksum_address(GTE_TOKENS["WETH"]["address"])
                token_address = self.web3.web3.to_checksum_address(GTE_TOKENS[target_token]["address"])
                
                path = [weth_address, token_address]
                swap_type = "native_token"
                logger.info(f"[{self.account_index}] Created ETH -> {target_token} path: {path}, swap type: {swap_type}")
            
            # CASE 2 & 3: If tokens have balance and we randomly chose to use them
            else:
                # Choose a random token with balance
                source_token_symbol = random.choice(list(tokens_with_balance.keys()))
                source_token_address = self.web3.web3.to_checksum_address(GTE_TOKENS[source_token_symbol]["address"])
                
                # 50% chance to swap to ETH, 50% chance to swap to another token
                swap_to_eth = random.choice([True, False])
                
                if swap_to_eth:
                    # CASE 2: Token -> ETH path
                    weth_address = self.web3.web3.to_checksum_address(GTE_TOKENS["WETH"]["address"])
                    path = [source_token_address, weth_address]
                    swap_type = "token_native"
                    logger.info(f"[{self.account_index}] Created {source_token_symbol} -> ETH path: {path}, swap type: {swap_type}")
                else:
                    # CASE 3: Token -> Token path
                    # Get available target tokens (excluding the source token and WETH)
                    available_targets = [token for token in GTE_TOKENS.keys() 
                                       if token != source_token_symbol and token != "WETH"]
                    
                    if available_targets:
                        target_token = random.choice(available_targets)
                        target_address = self.web3.web3.to_checksum_address(GTE_TOKENS[target_token]["address"])
                        
                        path = [source_token_address, target_address]
                        swap_type = "token_token"
                        logger.info(f"[{self.account_index}] Created {source_token_symbol} -> {target_token} path: {path}, swap type: {swap_type}")
                    else:
                        # Fallback: swap to ETH if no other tokens available
                        weth_address = self.web3.web3.to_checksum_address(GTE_TOKENS["WETH"]["address"])
                        path = [source_token_address, weth_address]
                        swap_type = "token_native"
                        logger.info(f"[{self.account_index}] Fallback: Created {source_token_symbol} -> ETH path: {path}, swap type: {swap_type}")
            
            return path, swap_type
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _get_path: {e}")
            return [], None

    @retry_async(default_value=False)
    async def _get_balances(self) -> dict:
        logger.info(f"[{self.account_index}] Getting balances")
        try:
            balances = {}
            # Multicall contract for balance checking
                     
            # Create multicall contract instance
            multicall_contract = self.web3.web3.eth.contract(
                address=self.web3.web3.to_checksum_address(BALANCE_CHECKER_CONTRACT_ADDRESS),
                abi=BALANCE_CHECKER_ABI
            )
            
            # Prepare token addresses list (include ETH as 0x0 address)
            token_addresses = [
                "0x0000000000000000000000000000000000000000"  # ETH address
            ]
            
            # Add all token addresses from GTE_TOKENS
            for token_symbol, token_data in GTE_TOKENS.items():
                token_addresses.append(self.web3.web3.to_checksum_address(token_data["address"]))
            
            # Prepare users list (single user in this case)
            users = [self.wallet.address]
            all_balances = await multicall_contract.functions.balances(
                users, token_addresses
            ).call()
            
            # ETH balance is the first one
            eth_balance = all_balances[0]
            balances["native"] = eth_balance
            logger.info(f"[{self.account_index}] Balance of ETH: {eth_balance}")
            
            # Process token balances
            token_symbols = list(GTE_TOKENS.keys())
            for i, token_symbol in enumerate(token_symbols):
                # Token balance is offset by 1 (since ETH is at index 0)
                token_balance = all_balances[i + 1]
                balances[token_symbol] = token_balance
                logger.info(f"[{self.account_index}] Balance of {token_symbol}: {token_balance}")
            
            return balances
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _get_balances: {e}")
            return False
    
    async def execute_swap(self):
        try:
            swaps_amount = random.randint(self.config.SWAPS.GTE.SWAPS_AMOUNT[0], self.config.SWAPS.GTE.SWAPS_AMOUNT[1])
            logger.info(f"[{self.account_index}] Planning to execute {swaps_amount} swaps")
            
            successful_swaps = 0
            
            for i in range(swaps_amount):
                logger.info(f"[{self.account_index}] Executing swap {i+1}/{swaps_amount}")
                
                balances = await self._get_balances()
                if not balances:
                    logger.error(f"[{self.account_index}] Failed to get balances")
                    continue
                
                # Regular swap logic first regardless of SWAP_ALL_TO_ETH setting
                path, swap_type = await self._get_path(balances)
                if not path or not swap_type:
                    logger.error(f"[{self.account_index}] Failed to generate valid path for swap")
                    continue
                
                # Execute the appropriate swap type
                swap_result = False
                if swap_type == "native_token":
                    swap_result = await self._swap_native_to_token(path)
                elif swap_type == "token_native":
                    swap_result = await self._swap_token_to_native(path, balances)
                elif swap_type == "token_token":
                    swap_result = await self._swap_token_to_token(path, balances)
                else:
                    logger.error(f"[{self.account_index}] Unknown swap type: {swap_type}")
                    continue
                
                if swap_result:
                    successful_swaps += 1
                    logger.success(f"[{self.account_index}] Swap {i+1} completed successfully")
                else:
                    logger.error(f"[{self.account_index}] Swap {i+1} failed")
                
                random_pause = random.randint(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
                )
                logger.info(
                    f"{self.account_index} | Waiting {random_pause} seconds before next swap..."
                )
                await asyncio.sleep(random_pause)
                
            # If SWAP_ALL_TO_ETH is enabled, swap all tokens to ETH after the loop
            if self.config.SWAPS.GTE.SWAP_ALL_TO_ETH:
                logger.info(f"[{self.account_index}] SWAP_ALL_TO_ETH enabled, now swapping all remaining tokens to ETH")
                
                # Get fresh balances after the previous swaps
                updated_balances = await self._get_balances()
                
                # Get tokens with non-zero balance (excluding native ETH)
                tokens_with_balance = {token: balance for token, balance in updated_balances.items() 
                                      if token != "native" and balance > 0}
                
                if not tokens_with_balance:
                    logger.info(f"[{self.account_index}] No tokens with balance found to swap to ETH")
                else:
                    # Swap each token to ETH one by one
                    for token_symbol, balance in tokens_with_balance.items():
                        logger.info(f"[{self.account_index}] Swapping {token_symbol} to ETH")
                        # Create path for this token to ETH
                        source_token_address = self.web3.web3.to_checksum_address(GTE_TOKENS[token_symbol]["address"])
                        weth_address = self.web3.web3.to_checksum_address(GTE_TOKENS["WETH"]["address"])
                        path = [source_token_address, weth_address]
                        
                        # Execute token to ETH swap
                        result = await self._swap_token_to_native(path, updated_balances)
                        if result:
                            successful_swaps += 1
                            logger.success(f"[{self.account_index}] Successfully swapped {token_symbol} to ETH")
                        else:
                            logger.error(f"[{self.account_index}] Failed to swap {token_symbol} to ETH")
                        
                        # Add a small delay between swaps
                        delay = random.uniform(self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0], self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1])
                        await asyncio.sleep(delay)
            
            # Return True if at least one swap was successful
            return successful_swaps > 0
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in execute_swap: {e}")
            return False
            
    async def _sign_and_send_transaction(self, tx, operation_name="transaction"):
        """Sign, send and wait for a transaction to be mined"""
        try:
            # Sign and send transaction
            signed_tx = self.web3.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await self.web3.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hash_hex = tx_hash.hex()
            explorer_link = f"{EXPLORER_URL_MEGAETH}{tx_hash_hex}"
            
            logger.info(f"[{self.account_index}] {operation_name} sent: {explorer_link}")
            
            # Wait for transaction to be mined
            receipt = await self.web3.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt.status == 1:
                logger.success(f"[{self.account_index}] {operation_name} successful! TX: {explorer_link}")
            else:
                logger.error(f"[{self.account_index}] {operation_name} failed! TX: {explorer_link}")
            
            return receipt
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _sign_and_send_transaction ({operation_name}): {e}")
            return None

    async def _calculate_min_output(self, path, amount_in, slippage_percentage=10):
        """
        Calculate the minimum output amount based on current prices and slippage tolerance
        
        Args:
            path: The swap path [from_token, to_token]
            amount_in: The input amount, could be an integer or Balance object
            slippage_percentage: Allowed slippage percentage (default: 10%)
            
        Returns:
            int: The minimum output amount after slippage
        """
        try:
            # Convert amount_in to int if it's a Balance object
            if hasattr(amount_in, 'wei'):
                amount_in = amount_in.wei
            # Otherwise ensure it's still an integer
            elif not isinstance(amount_in, int):
                amount_in = int(amount_in)
            
            # Ensure path addresses are checksum
            checksum_path = [self.web3.web3.to_checksum_address(addr) for addr in path]
            
            # Get expected output amounts for the path
            amounts = await self.contract.functions.getAmountsOut(
                amount_in,
                checksum_path
            ).call()
            
            # The last amount in the array is the expected output amount
            expected_output = amounts[-1]
            
            # Calculate minimum output with slippage tolerance using integer division
            min_output = expected_output * (100 - slippage_percentage) // 100
            
            logger.info(f"[{self.account_index}] Expected output: {expected_output}, Min output after {slippage_percentage}% slippage: {min_output}")
            
            return min_output
        except Exception as e:
            logger.warning(f"[{self.account_index}] Error calculating min output: {e}. Using 0 as fallback.")
            return 0

    async def _swap_native_to_token(self, path):
        """Execute ETH -> Token swap"""
        try:
            # Get target token info (the token we're swapping to)
            target_token_address = self.web3.web3.to_checksum_address(path[1])
            target_token_symbol, _, _ = await self._get_token_info(target_token_address, {}, "target")
            
            # Get the current ETH balance - this returns a Balance object
            eth_balance = await self.web3.get_balance(self.wallet.address)
            # Convert the Balance object to an integer in wei
            eth_balance_wei = eth_balance.wei
            
            # Get percentage range from config, or use default if not available
            percentage_range = self.config.SWAPS.GTE.BALANCE_PERCENTAGE_TO_SWAP
            swap_percentage = random.uniform(percentage_range[0], percentage_range[1])
            
            # Calculate amount to swap (percentage of balance) using integer math
            amount_eth = int(eth_balance_wei * swap_percentage / 100)
            
            # Make sure we're not trying to swap the entire balance (leave some for gas)
            max_amount = int(eth_balance_wei * 0.9)  # Max 90% of balance
            amount_eth = min(amount_eth, max_amount)
            

            logger.info(f"[{self.account_index}] Executing ETH -> {target_token_symbol} swap with {amount_eth} wei ({swap_percentage:.2f}% of balance)")
            
            gas = await self.web3.get_gas_params()
            deadline = int(time.time()) + 20 * 60

            # Get the current nonce for the address
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            logger.info(f"[{self.account_index}] Using nonce {nonce} for ETH -> {target_token_symbol} swap")

            # Ensure path addresses are checksum
            checksum_path = [self.web3.web3.to_checksum_address(addr) for addr in path]
            
            # Calculate minimum output amount with slippage tolerance
            min_output = await self._calculate_min_output(checksum_path, amount_eth, 10)

            # Build transaction without gas limit first
            tx = await self.contract.functions.swapExactETHForTokens(
                min_output,  # Use calculated min amount instead of 0
                checksum_path,
                self.wallet.address,
                deadline
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "value": amount_eth,
                    "nonce": nonce,
                    **gas,
                }
            )
            
            # Estimate gas dynamically
            tx["gas"] = await self.web3.estimate_gas(tx)
            logger.info(f"[{self.account_index}] Estimated gas for ETH -> {target_token_symbol} swap: {tx['gas']}")
            
            receipt = await self._sign_and_send_transaction(tx, f"Swap ETH -> {target_token_symbol}")
            return receipt and receipt.status == 1
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _swap_native_to_token: {e}")
            return False
            
    async def _get_token_info(self, token_address, balances, position="source"):
        """
        Helper function to get token symbol and balance from address
        
        Args:
            token_address: The token address to get info for
            balances: Dictionary of token balances
            position: Whether this is a source or target token (for logging)
            
        Returns:
            tuple: (token_symbol, token_balance, decimals)
        """
        try:
            # Ensure the address is in checksum format for comparison
            checksum_address = self.web3.web3.to_checksum_address(token_address)
            
            # Find the token symbol by comparing addresses (case-insensitive)
            token_symbol = next(symbol for symbol, data in GTE_TOKENS.items()
                                if self.web3.web3.to_checksum_address(data["address"]).lower() == checksum_address.lower())
            
            # Get token balance and decimals
            token_balance = balances.get(token_symbol, 0)
            token_decimals = GTE_TOKENS[token_symbol]["decimals"]
            
            logger.info(f"[{self.account_index}] {position.capitalize()} token: {token_symbol}, balance: {token_balance}, decimals: {token_decimals}")
            
            return token_symbol, token_balance, token_decimals
        except Exception as e:
            logger.error(f"[{self.account_index}] Error getting token info for {token_address}: {e}")
            raise e

    async def _swap_token_to_native(self, path, balances):
        """Execute Token -> ETH swap"""
        try:
            # Get source token info
            source_token_address = self.web3.web3.to_checksum_address(path[0])
            source_token_symbol, token_balance, _ = await self._get_token_info(source_token_address, balances, "source")
            
            # Ensure token_balance is an integer
            token_balance = int(token_balance)
            
            # Use 100% of the token balance for the swap
            amount_in = token_balance
            
            if amount_in == 0:
                logger.error(f"[{self.account_index}] Not enough balance for {source_token_symbol} to swap")
                return False
                
            logger.info(f"[{self.account_index}] Executing Token -> ETH swap with {amount_in} {source_token_symbol} (100% of balance)")
            
            gas = await self.web3.get_gas_params()
            deadline = int(time.time()) + 20 * 60
            
            # Get the current nonce for the address
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            logger.info(f"[{self.account_index}] Using nonce {nonce} for approval")
            
            # Create token contract for approval
            token_contract = self.web3.web3.eth.contract(address=source_token_address, abi=ERC20_ABI)
            
            # Build approval transaction without gas limit first
            approval_tx = await token_contract.functions.approve(
                self.web3.web3.to_checksum_address(GTE_SWAPS_CONTRACT),
                amount_in
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    **gas,
                }
            )
            
            # Estimate gas for approval
            approval_tx["gas"] = await self.web3.estimate_gas(approval_tx)
            logger.info(f"[{self.account_index}] Estimated gas for token approval: {approval_tx['gas']}")
            
            # Sign and send approval
            approval_receipt = await self._sign_and_send_transaction(approval_tx, f"Approve {source_token_symbol}")
            if not approval_receipt or approval_receipt.status != 1:
                logger.error(f"[{self.account_index}] Approval transaction failed")
                return False
            
            # Increment nonce for the next transaction
            nonce += 1
            logger.info(f"[{self.account_index}] Using nonce {nonce} for Token -> ETH swap")
            
            # Ensure path addresses are checksum
            checksum_path = [self.web3.web3.to_checksum_address(addr) for addr in path]
            
            # Calculate minimum output amount with slippage tolerance
            min_output = await self._calculate_min_output(checksum_path, amount_in, 10)
            
            # Build swap transaction without gas limit first
            tx = await self.contract.functions.swapExactTokensForETH(
                amount_in,
                min_output,  # Use calculated min amount instead of 0
                checksum_path,
                self.wallet.address,
                deadline
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    **gas,
                }
            )
            
            # Estimate gas for swap
            tx["gas"] = await self.web3.estimate_gas(tx)
            logger.info(f"[{self.account_index}] Estimated gas for Token -> ETH swap: {tx['gas']}")
            
            receipt = await self._sign_and_send_transaction(tx, f"Swap {source_token_symbol} -> ETH")
            return receipt and receipt.status == 1
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _swap_token_to_native: {e}")
            return False
            
    async def _swap_token_to_token(self, path, balances):
        """Execute Token -> Token swap"""
        try:
            # Get source token info
            source_token_address = self.web3.web3.to_checksum_address(path[0])
            source_token_symbol, token_balance, _ = await self._get_token_info(source_token_address, balances, "source")
            
            # Get target token info
            target_token_address = self.web3.web3.to_checksum_address(path[1])
            target_token_symbol, _, _ = await self._get_token_info(target_token_address, balances, "target")
            
            # Ensure token_balance is an integer
            token_balance = int(token_balance)
            
            # Use 100% of the token balance for the swap
            amount_in = token_balance
            
            if amount_in == 0:
                logger.error(f"[{self.account_index}] Not enough balance for {source_token_symbol} to swap")
                return False
                
            logger.info(f"[{self.account_index}] Executing Token -> Token swap with {amount_in} {source_token_symbol} (100% of balance) to {target_token_symbol}")
            
            gas = await self.web3.get_gas_params()
            deadline = int(time.time()) + 20 * 60
            
            # Get the current nonce for the address
            nonce = await self.web3.web3.eth.get_transaction_count(self.wallet.address)
            logger.info(f"[{self.account_index}] Using nonce {nonce} for approval")
            
            # Create token contract for approval
            token_contract = self.web3.web3.eth.contract(address=source_token_address, abi=ERC20_ABI)
            
            # Build approval transaction without gas limit first
            approval_tx = await token_contract.functions.approve(
                self.web3.web3.to_checksum_address(GTE_SWAPS_CONTRACT),
                amount_in
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    **gas,
                }
            )
            
            # Estimate gas for approval
            approval_tx["gas"] = await self.web3.estimate_gas(approval_tx)
            logger.info(f"[{self.account_index}] Estimated gas for token approval: {approval_tx['gas']}")
            
            # Sign and send approval
            approval_receipt = await self._sign_and_send_transaction(approval_tx, f"Approve {source_token_symbol}")
            if not approval_receipt or approval_receipt.status != 1:
                logger.error(f"[{self.account_index}] Approval transaction failed")
                return False
            
            # Increment nonce for the next transaction
            nonce += 1
            logger.info(f"[{self.account_index}] Using nonce {nonce} for Token -> Token swap")
            
            # Ensure path addresses are checksum
            checksum_path = [self.web3.web3.to_checksum_address(addr) for addr in path]
            
            # Calculate minimum output amount with slippage tolerance
            min_output = await self._calculate_min_output(checksum_path, amount_in, 10)
            
            # Build swap transaction without gas limit first
            tx = await self.contract.functions.swapExactTokensForTokens(
                amount_in,
                min_output,  # Use calculated min amount instead of 0
                checksum_path,
                self.wallet.address,
                deadline
            ).build_transaction(
                {
                    "from": self.wallet.address,
                    "nonce": nonce,
                    **gas,
                }
            )
            
            # Estimate gas for swap
            tx["gas"] = await self.web3.estimate_gas(tx)
            logger.info(f"[{self.account_index}] Estimated gas for Token -> Token swap: {tx['gas']}")
            
            receipt = await self._sign_and_send_transaction(tx, f"Swap {source_token_symbol} -> {target_token_symbol}")
            return receipt and receipt.status == 1
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in _swap_token_to_token: {e}")
            return False

