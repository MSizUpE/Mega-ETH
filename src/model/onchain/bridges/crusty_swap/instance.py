import random
from eth_account import Account
from src.model.onchain.web3_custom import Web3Custom
from loguru import logger
import primp
import asyncio
from src.utils.config import Config
from web3 import AsyncWeb3
from eth_account import Account
from src.model.onchain.bridges.crusty_swap.constants import (
    CONTRACT_ADDRESSES, 
    DESTINATION_CONTRACT_ADDRESS,
    CRUSTY_SWAP_ABI,
    CHAINLINK_ETH_PRICE_CONTRACT_ADDRESS,
    CHAINLINK_ETH_PRICE_ABI,
    ZERO_ADDRESS,
    CRUSTY_SWAP_RPCS
)
from src.utils.constants import EXPLORER_URLS
from typing import Dict

class CrustySwap:
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
        self.megaeth_web3 = web3
        self.config = config
        self.wallet = wallet
        self.proxy = proxy
        self.private_key = private_key

        self.eth_web3 = None
        self.megaeth_contract = self.megaeth_web3.web3.eth.contract(address=DESTINATION_CONTRACT_ADDRESS, abi=CRUSTY_SWAP_ABI)

    async def initialize(self):
        try:
            self.eth_web3 = await self.create_web3("Ethereum")
            return True
        except Exception as e:
            logger.error(f"{self.account_index} | Error: {e}")
            return False

    async def create_web3(self, network: str) -> AsyncWeb3:
        try:
            web3 = await Web3Custom.create(
                self.account_index,
                [CRUSTY_SWAP_RPCS[network]],
                self.config.OTHERS.USE_PROXY_FOR_RPC,
                self.proxy,
                self.config.OTHERS.SKIP_SSL_VERIFICATION,
            )
            return web3
        except Exception as e:
            logger.error(f"{self.account_index} | Error: {e}")
            return False
        
    async def get_megaeth_balance(self) -> float:
        """Get native MEGAETH balance."""
        try:
            balance_wei = await self.megaeth_web3.web3.eth.get_balance(self.wallet.address)
            return float(self.megaeth_web3.web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to get MEGAETH balance: {str(e)}")
            return 0

    async def get_native_balance(self, network: str) -> float:
        """Get native token balance for a specific network."""
        try:
            web3 = await self.create_web3(network)
            return await web3.web3.eth.get_balance(self.wallet.address)
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to get balance for {network}: {str(e)}")
            return None

    async def wait_for_balance_increase(self, initial_balance: float) -> bool:
        """Wait for MEGAETH balance to increase after refuel."""
        # Use the timeout from config
        timeout = self.config.CRUSTY_SWAP.MAX_WAIT_TIME
        
        logger.info(f"[{self.account_index}] Waiting for balance to increase (max wait time: {timeout} seconds)...")
        start_time = asyncio.get_event_loop().time()
        
        # Check balance every 5 seconds until timeout
        while asyncio.get_event_loop().time() - start_time < timeout:
            current_balance = await self.get_megaeth_balance()
            if current_balance > initial_balance:
                logger.success(
                    f"[{self.account_index}] Balance increased from {initial_balance:.9f} to {current_balance:.9f} MEGAETH"
                )
                return True
            
            # Log progress every 15 seconds
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % 15 == 0:
                logger.info(f"[{self.account_index}] Still waiting for balance to increase... ({elapsed}/{timeout} seconds)")
            
            await asyncio.sleep(5)
        
        logger.error(f"[{self.account_index}] Balance didn't increase after {timeout} seconds")
        return False
    
    async def get_gas_params(self, web3: AsyncWeb3) -> Dict[str, int]:
        """Get gas parameters for transaction."""
        latest_block = await web3.web3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = await web3.web3.eth.max_priority_fee
        max_fee = int((base_fee + max_priority_fee) * 1.5)
        
        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }
    
    async def get_minimum_deposit(self, network: str) -> int:
        """Get minimum deposit amount for a specific network."""
        try:
            web3 = await self.create_web3(network)
            contract = web3.web3.eth.contract(address=CONTRACT_ADDRESSES[network], abi=CRUSTY_SWAP_ABI)
            return await contract.functions.minimumDeposit().call()
        except Exception as e:
            logger.error(f"[{self.account_index}] Error getting minimum deposit: {str(e)}")
            return 0
        
    async def get_eligible_networks(self, max_retries=5, retry_delay=5):
        """
        Get eligible networks for refueling with retry mechanism.
        
        Args:
            max_retries: Maximum number of retry attempts (default: 5)
            retry_delay: Delay between retries in seconds (default: 5)
            
        Returns:
            List of tuples (network, balance) or False if no eligible networks found
        """
        for attempt in range(1, max_retries + 1):
            try:
                eligible_networks = []
                
                networks_to_refuel_from = self.config.CRUSTY_SWAP.NETWORKS_TO_REFUEL_FROM
                for network in networks_to_refuel_from:
                    balance = await self.get_native_balance(network)
                    if balance > await self.get_minimum_deposit(network):
                        eligible_networks.append((network, balance))
                return eligible_networks
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"[{self.account_index}] Attempt {attempt}/{max_retries} failed to get eligible networks: {str(e)}")
                    logger.info(f"[{self.account_index}] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"[{self.account_index}] All {max_retries} attempts failed to get eligible networks: {str(e)}")
                    return False
        
        # We should never reach here, but just in case
        return False

    async def pick_network_to_refuel_from(self):
        eligible_networks = await self.get_eligible_networks()
        if not eligible_networks:
            logger.info(f"[{self.account_index}] No eligible networks found")
            return False
        return random.choice(eligible_networks)

    
    async def refuel(self) -> bool:
        """Refuel MEGAETH from one of the supported networks."""
        try:
            await self.initialize()
            # Get current MEGAETH balance before refuel
            initial_balance = await self.get_megaeth_balance()
            logger.info(f"[{self.account_index}] Initial MEGAETH balance: {initial_balance:.9f}")
            if initial_balance > self.config.CRUSTY_SWAP.MINIMUM_BALANCE_TO_REFUEL:
                logger.info(f"[{self.account_index}] Current balance ({initial_balance:.9f}) is above minimum "
                    f"({self.config.CRUSTY_SWAP.MINIMUM_BALANCE_TO_REFUEL}), skipping refuel"
                )
                return False
            
            network_info = await self.pick_network_to_refuel_from()
            if not network_info:
                logger.error(f"[{self.account_index}] No network found")
                return False
                
            network, balance = network_info
            
            # Get web3 for the selected network
            web3 = await self.create_web3(network)
            gas_params = await self.get_gas_params(web3)
            contract = web3.web3.eth.contract(address=CONTRACT_ADDRESSES[network], abi=CRUSTY_SWAP_ABI)
            
            # Estimate gas using the same gas parameters from get_balances
            gas_estimate = await web3.web3.eth.estimate_gas({
                'from': self.wallet.address,
                'to': CONTRACT_ADDRESSES[network],
                'value': await contract.functions.minimumDeposit().call(),
                'data': contract.functions.deposit(
                        ZERO_ADDRESS,
                        self.wallet.address
                    )._encode_transaction_data(),
            })

            if self.config.CRUSTY_SWAP.BRIDGE_ALL:
                # Calculate exact gas units needed (same as tx)
                gas_units = int(gas_estimate * 1.2)
                
                # Calculate maximum possible gas cost
                max_total_gas_cost = (gas_units * gas_params['maxFeePerGas']) * random.uniform(1.15, 1.2)
                max_total_gas_cost = int(max_total_gas_cost + web3.web3.to_wei(random.uniform(0.00001, 0.00002), 'ether'))
                
                # Calculate amount we can send
                amount_wei = balance - max_total_gas_cost

                if web3.web3.from_wei(amount_wei, 'ether') > self.config.CRUSTY_SWAP.BRIDGE_ALL_MAX_AMOUNT:
                    amount_wei = int(web3.web3.to_wei(self.config.CRUSTY_SWAP.BRIDGE_ALL_MAX_AMOUNT * (random.uniform(0.95, 0.99)), 'ether'))
                    
                # Double check our math
                total_needed = amount_wei + max_total_gas_cost

                # Verify we have enough for the transaction
                if total_needed > balance:
                    raise Exception(f"Insufficient funds. Have: {balance}, Need: {total_needed}, Difference: {total_needed - balance}")
            else:
                amount_ether = random.uniform(
                    self.config.CRUSTY_SWAP.AMOUNT_TO_REFUEL[0], 
                    self.config.CRUSTY_SWAP.AMOUNT_TO_REFUEL[1]
                    )
                
                amount_wei = int(round(web3.web3.to_wei(amount_ether, 'ether'), random.randint(8, 12)))
                
            # Get nonce
            nonce = await web3.web3.eth.get_transaction_count(self.wallet.address)
            
            has_enough_megaeth = await self.check_available_megaeth(amount_wei, contract)
            if not has_enough_megaeth:
                logger.error(f"[{self.account_index}] Not enough MEGAETH in the contract for your amount of ETH deposit, try again later")
                return False
                
            tx = {
                'from': self.wallet.address,
                'to': CONTRACT_ADDRESSES[network],
                'value': amount_wei,
                'data': contract.functions.deposit(
                        ZERO_ADDRESS,
                        self.wallet.address
                    )._encode_transaction_data(),
                'nonce': nonce,
                'gas': int(gas_estimate * 1.1),  # Add 10% buffer to gas estimate
                'chainId': await web3.web3.eth.chain_id,
                **gas_params  # Use the same gas params that we calculated during get_balances
            }
            
            # Sign and send transaction
            signed_tx = web3.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await web3.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"[{self.account_index}] Waiting for refuel transaction confirmation...")
            receipt = await web3.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            explorer_url = f"{EXPLORER_URLS[network]}{tx_hash.hex()}"
            
            if receipt['status'] == 1:
                logger.success(f"[{self.account_index}] Refuel transaction successful! Explorer URL: {explorer_url}")
                
                # Wait for balance to increase if configured to do so
                if self.config.CRUSTY_SWAP.WAIT_FOR_FUNDS_TO_ARRIVE:
                    logger.success(f"[{self.account_index}] Waiting for balance increase...")
                    if await self.wait_for_balance_increase(initial_balance):
                        logger.success(f"[{self.account_index}] Successfully refueled from {network}")
                        return True
                    logger.warning(f"[{self.account_index}] Balance didn't increase, but transaction was successful")
                    return True
                else:
                    logger.success(f"[{self.account_index}] Successfully refueled from {network} (not waiting for balance)")
                    return True
            else:
                logger.error(f"[{self.account_index}] Refuel transaction failed! Explorer URL: {explorer_url}")
                return False
                
        except Exception as e:
            logger.error(f"[{self.account_index}] Refuel failed: {str(e)}")
            return False

    def _convert_private_keys_to_addresses(self, private_keys_to_distribute):
        """Convert private keys to addresses."""
        addresses = []
        for private_key in private_keys_to_distribute:
            addresses.append(Account.from_key(private_key).address)
        return addresses

    async def check_available_megaeth(self, eth_amount_wei, contract, max_retries=5, retry_delay=5) -> bool:
        """
        Check if there is enough MEGAETH in the Crusty Swap contract to fill a buy order.
        Includes retry mechanism for resilience against temporary failures.
        
        Args:
            eth_amount_wei: Amount of ETH in wei to be used for the purchase
            contract: The Crusty Swap contract
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            
        Returns:
            bool: True if there is enough MEGAETH, False otherwise
        """
        for attempt in range(1, max_retries + 1):
            try:
                # Get available MEGAETH in the contract
                available_megaeth_wei = await self.megaeth_web3.web3.eth.get_balance(DESTINATION_CONTRACT_ADDRESS)
                
                # Get ETH price from Chainlink (in USD with 8 decimals)
                chainlink_eth_price_contract = self.eth_web3.web3.eth.contract(
                    address=CHAINLINK_ETH_PRICE_CONTRACT_ADDRESS, 
                    abi=CHAINLINK_ETH_PRICE_ABI
                )
                eth_price_usd = await chainlink_eth_price_contract.functions.latestAnswer().call()
                
                # Get MEGAETH price from contract (in USD with 8 decimals)
                megaeth_price_usd = await contract.functions.pricePerETH().call()
                
                # Calculate how many MEGAETH we should receive for our ETH
                # Convert ETH to USD value with proper decimal handling
                eth_amount_ether = eth_amount_wei / 10**18
                eth_price_usd_real = eth_price_usd / 10**8  # Convert to real USD value
                eth_value_usd = eth_amount_ether * eth_price_usd_real
                
                # Calculate MEGAETH amount from USD value
                megaeth_price_usd_real = megaeth_price_usd / 10**8  # Convert to real USD value
                expected_megaeth_amount = eth_value_usd / megaeth_price_usd_real
                expected_megaeth_amount_wei = int(expected_megaeth_amount * 10**18)
                
                logger.info(f"[{self.account_index}] ETH amount: {eth_amount_ether} ETH (${eth_value_usd:.2f})")
                logger.info(f"[{self.account_index}] ETH price: ${eth_price_usd_real:.2f}")
                logger.info(f"[{self.account_index}] MEGAETH price: ${megaeth_price_usd_real:.4f}")
                logger.info(f"[{self.account_index}] Available MEGAETH: {self.megaeth_web3.web3.from_wei(available_megaeth_wei, 'ether')} MEGAETH")
                logger.info(f"[{self.account_index}] Expected to receive: {expected_megaeth_amount:.4f} MEGAETH")
                
                # Check if there's enough MEGAETH in the contract
                has_enough_megaeth = available_megaeth_wei >= expected_megaeth_amount_wei
                
                if has_enough_megaeth:
                    logger.success(f"[{self.account_index}] Contract has enough MEGAETH to fill the order")
                else:
                    logger.warning(f"[{self.account_index}] Contract doesn't have enough MEGAETH! " 
                                f"Available: {self.megaeth_web3.web3.from_wei(available_megaeth_wei, 'ether')} MEGAETH, "
                                f"Needed: {expected_megaeth_amount:.4f} MEGAETH")
                    
                return has_enough_megaeth
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"[{self.account_index}] Attempt {attempt}/{max_retries} failed to check available MEGAETH: {str(e)}")
                    logger.info(f"[{self.account_index}] Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(f"[{self.account_index}] All {max_retries} attempts failed to check available MEGAETH: {str(e)}")
                    return False
        
        # We should never reach here, but just in case
        return False

    async def _get_megaeth_balance(self, address) -> float:
        """Get native MEGAETH balance for a specific address."""
        try:
            balance_wei = await self.megaeth_web3.web3.eth.get_balance(address)
            return float(self.megaeth_web3.web3.from_wei(balance_wei, 'ether'))
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to get MEGAETH balance: {str(e)}")
            return None
            
    async def _wait_for_balance_increase(self, initial_balance: float, address: str) -> bool:
        """Wait for MEGAETH balance to increase after refuel."""
        # Use the timeout from config
        timeout = self.config.CRUSTY_SWAP.MAX_WAIT_TIME
        
        logger.info(f"[{self.account_index}] Waiting for balance to increase (max wait time: {timeout} seconds)...")
        start_time = asyncio.get_event_loop().time()
        
        # Check balance every 5 seconds until timeout
        while asyncio.get_event_loop().time() - start_time < timeout:
            current_balance = await self._get_megaeth_balance(address)
            if current_balance > initial_balance:
                logger.success(
                    f"[{self.account_index}] Balance increased from {initial_balance} to {current_balance} MEGAETH"
                )
                return True
            
            # Log progress every 15 seconds
            elapsed = int(asyncio.get_event_loop().time() - start_time)
            if elapsed % 15 == 0:
                logger.info(f"[{self.account_index}] Still waiting for balance to increase... ({elapsed}/{timeout} seconds)")
            
            await asyncio.sleep(5)
        
        logger.error(f"[{self.account_index}] Balance didn't increase after {timeout} seconds")
        return False
        
    async def _handle_transaction_status(self, receipt, explorer_url, initial_balance, network, address) -> bool:
        if receipt['status'] == 1:
            logger.success(f"[{self.account_index}] Refuel transaction successful! Explorer URL: {explorer_url}")
            
            # Wait for balance to increase if configured to do so
            if self.config.CRUSTY_SWAP.WAIT_FOR_FUNDS_TO_ARRIVE:
                logger.success(f"[{self.account_index}] Waiting for balance increase...")
                if await self._wait_for_balance_increase(initial_balance, address):
                    logger.success(f"[{self.account_index}] Successfully refueled from {network}")
                    return True
                logger.warning(f"[{self.account_index}] Balance didn't increase, but transaction was successful")
                return True
            else:
                logger.success(f"[{self.account_index}] Successfully refueled from {network} (not waiting for balance)")
                return True
        else:
            logger.error(f"[{self.account_index}] Refuel transaction failed! Explorer URL: {explorer_url}")
            return False
            
    async def send_refuel_from_one_to_all(self, address) -> bool:
        """Send a refuel transaction from one of the supported networks."""
        try:
            initial_balance = await self._get_megaeth_balance(address)
            if initial_balance is None:
                logger.error(f"[{self.account_index}] Failed to get MEGAETH balance for address: {address}")
                return False
            logger.info(f"[{self.account_index}] Initial MEGAETH balance: {initial_balance}")
            if initial_balance > self.config.CRUSTY_SWAP.MINIMUM_BALANCE_TO_REFUEL:
                logger.info(f"[{self.account_index}] Current balance ({initial_balance}) is above minimum "
                    f"({self.config.CRUSTY_SWAP.MINIMUM_BALANCE_TO_REFUEL}), skipping refuel"
                )
                return False
                
            network_info = await self.pick_network_to_refuel_from()
            if not network_info:
                logger.error(f"[{self.account_index}] No network found")
                return False
                
            network, balance = network_info
            
            # Get web3 for the selected network
            web3 = await self.create_web3(network)
            gas_params = await self.get_gas_params(web3)
            contract = web3.web3.eth.contract(address=CONTRACT_ADDRESSES[network], abi=CRUSTY_SWAP_ABI)
            
            # Estimate gas using the same gas parameters
            gas_estimate = await web3.web3.eth.estimate_gas({
                'from': self.wallet.address,
                'to': CONTRACT_ADDRESSES[network],
                'value': await contract.functions.minimumDeposit().call(),
                'data': contract.functions.deposit(
                        ZERO_ADDRESS,
                        address
                    )._encode_transaction_data(),
            })

            if self.config.CRUSTY_SWAP.BRIDGE_ALL:
                # Calculate exact gas units needed (same as tx)
                gas_units = int(gas_estimate * 1.2)
                
                # Calculate maximum possible gas cost
                max_total_gas_cost = (gas_units * gas_params['maxFeePerGas']) * random.uniform(1.15, 1.2)
                max_total_gas_cost = int(max_total_gas_cost + web3.web3.to_wei(random.uniform(0.00001, 0.00002), 'ether'))

                
                # Calculate amount we can send
                amount_wei = balance - max_total_gas_cost

                if web3.web3.from_wei(amount_wei, 'ether') > self.config.CRUSTY_SWAP.BRIDGE_ALL_MAX_AMOUNT:
                    amount_wei = int(web3.web3.to_wei(self.config.CRUSTY_SWAP.BRIDGE_ALL_MAX_AMOUNT * (random.uniform(0.95, 0.99)), 'ether'))
                # Double check our math
                total_needed = amount_wei + max_total_gas_cost

                # Verify we have enough for the transaction
                if total_needed > balance:
                    raise Exception(f"Insufficient funds. Have: {balance}, Need: {total_needed}, Difference: {total_needed - balance}")
            else:
                amount_ether = random.uniform(
                    self.config.CRUSTY_SWAP.AMOUNT_TO_REFUEL[0], 
                    self.config.CRUSTY_SWAP.AMOUNT_TO_REFUEL[1]
                    )
                
                amount_wei = int(round(web3.web3.to_wei(amount_ether, 'ether'), random.randint(8, 12)))
                
            # Get nonce
            nonce = await web3.web3.eth.get_transaction_count(self.wallet.address)
            has_enough_megaeth = await self.check_available_megaeth(amount_wei, contract)
            if not has_enough_megaeth:
                logger.error(f"[{self.account_index}] Not enough MEGAETH in the contract for your amount of ETH deposit, try again later")
                return False
                
            tx = {
                'from': self.wallet.address,
                'to': CONTRACT_ADDRESSES[network],
                'value': amount_wei,
                'data': contract.functions.deposit(
                        ZERO_ADDRESS,
                        address
                    )._encode_transaction_data(),
                'nonce': nonce,
                'gas': int(gas_estimate * 1.1),  # Add 10% buffer to gas estimate
                'chainId': await web3.web3.eth.chain_id,
                **gas_params  # Use the same gas params that we calculated during get_balances
            }
            
            # Sign and send transaction
            signed_tx = web3.web3.eth.account.sign_transaction(tx, self.private_key)
            tx_hash = await web3.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
            
            logger.info(f"[{self.account_index}] Waiting for refuel transaction confirmation...")
            receipt = await web3.web3.eth.wait_for_transaction_receipt(tx_hash)
            
            explorer_url = f"{EXPLORER_URLS[network]}{tx_hash.hex()}"
            return await self._handle_transaction_status(receipt, explorer_url, initial_balance, network, address)

        except Exception as e:
            logger.error(f"[{self.account_index}] Refuel failed: {str(e)}")
            return False

    async def refuel_from_one_to_all(self, private_keys_to_distribute) -> bool:
        """Refuel MEGAETH from one of the supported networks to multiple addresses."""
        try:
            await self.initialize()
            addresses = self._convert_private_keys_to_addresses(private_keys_to_distribute)
            for index, address in enumerate(addresses):
                logger.info(f"[{self.account_index}] - [{index}/{len(addresses)}] Refueling from MAIN: {self.wallet.address} to: {address} ")
                status = await self.send_refuel_from_one_to_all(address)
                pause = random.uniform(
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[0], 
                    self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS[1]
                )
                await asyncio.sleep(pause)
            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] Refuel failed: {str(e)}")
            return False