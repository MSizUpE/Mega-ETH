import random
import ccxt.async_support as ccxt
import asyncio
import time
from decimal import Decimal
from src.utils.config import Config
from eth_account import Account
from loguru import logger
from web3 import Web3
from src.model.offchain.cex.constants import (
    CEX_WITHDRAWAL_RPCS,
    NETWORK_MAPPINGS,
    EXCHANGE_PARAMS,
    SUPPORTED_EXCHANGES
)
from typing import Dict, Optional


class CexWithdraw:
    def __init__(self, account_index: int, private_key: str, config: Config):
        self.account_index = account_index
        self.private_key = private_key
        self.config = config
        
        # Setup exchange based on config
        exchange_name = config.EXCHANGES.name.lower()
        if exchange_name not in SUPPORTED_EXCHANGES:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
            
        # Initialize exchange
        self.exchange = getattr(ccxt, exchange_name)()
            
        # Setup exchange credentials
        self.exchange.apiKey = config.EXCHANGES.apiKey
        self.exchange.secret = config.EXCHANGES.secretKey
        if config.EXCHANGES.passphrase:
            self.exchange.password = config.EXCHANGES.passphrase
        
        self.account = Account.from_key(private_key)
        self.address = self.account.address
        
        # Get withdrawal network from config
        if not self.config.EXCHANGES.withdrawals:
            raise ValueError("No withdrawal configurations found")
            
        withdrawal_config = self.config.EXCHANGES.withdrawals[0]
        if not withdrawal_config.networks:
            raise ValueError("No networks specified in withdrawal configuration")
            
        # The network will be selected during withdrawal, not in __init__
        # We'll initialize web3 only after network selection in the withdraw method
        self.network = None
        self.web3 = None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.check_auth()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.exchange.close()

    async def check_auth(self) -> None:
        """Test exchange authentication"""
        logger.info(f"[{self.account_index}] Testing exchange authentication...")
        try:
            await self.exchange.fetch_balance()
            logger.success(f"[{self.account_index}] Authentication successful")
        except ccxt.AuthenticationError as e:
            logger.error(f"[{self.account_index}] Authentication error: {str(e)}")
            await self.exchange.close()
            raise
        except Exception as e:
            logger.error(f"[{self.account_index}] Unexpected error during authentication: {str(e)}")
            await self.exchange.close()
            raise
            
    async def get_chains_info(self) -> Dict:
        """Get withdrawal networks information"""
        logger.info(f"[{self.account_index}] Getting withdrawal networks data...")
        
        try:
            await self.exchange.load_markets()
            
            chains_info = {}
            withdrawal_config = self.config.EXCHANGES.withdrawals[0]
            currency = withdrawal_config.currency.upper()
            
            if currency not in self.exchange.currencies:
                logger.error(f"[{self.account_index}] Currency {currency} not found on {self.config.EXCHANGES.name}")
                return {}
                
            networks = self.exchange.currencies[currency]["networks"]
            # logger.info(f"[{self.account_index}] Available networks for {currency}:")
            
            for key, info in networks.items():
                withdraw_fee = info["fee"]
                withdraw_min = info["limits"]["withdraw"]["min"]
                network_id = info["id"]
                
                logger.info(f"[{self.account_index}]   - Network: {key} (ID: {network_id})")
                logger.info(f"[{self.account_index}]     Fee: {withdraw_fee}, Min Amount: {withdraw_min}")
                logger.info(f"[{self.account_index}]     Enabled: {info['withdraw']}")
                
                if info["withdraw"]:
                    chains_info[key] = {
                        "chainId": network_id,
                        "withdrawEnabled": True,
                        "withdrawFee": withdraw_fee,
                        "withdrawMin": withdraw_min
                    }
                        
            return chains_info
        except Exception as e:
            logger.error(f"[{self.account_index}] Error getting chains info: {str(e)}")
            await self.exchange.close()
            raise
        
    def _is_withdrawal_enabled(self, key: str, info: Dict) -> bool:
        """Check if withdrawal is enabled for the network"""
        return info["withdraw"]
        
    def _get_chain_id(self, key: str, info: Dict) -> str:
        """Get network chain ID"""
        return info["id"]
        
    def _get_withdraw_fee(self, info: Dict) -> float:
        """Get withdrawal fee"""
        return info["fee"]
        
    @staticmethod
    def _get_withdraw_min(info: Dict) -> float:
        """Get minimum withdrawal amount"""
        return info["limits"]["withdraw"]["min"]
        
    async def check_balance(self, amount: float) -> bool:
        """Check if exchange has enough balance for withdrawal"""
        try:
            # Get exchange-specific balance parameters
            exchange_name = self.config.EXCHANGES.name.lower()
            params = EXCHANGE_PARAMS[exchange_name]["balance"]
            
            balances = await self.exchange.fetch_balance(params=params)
            withdrawal_config = self.config.EXCHANGES.withdrawals[0]
            currency = withdrawal_config.currency.upper()
            
            balance = float(balances[currency]["total"])
            logger.info(f"[{self.account_index}] Exchange balance: {balance:.8f} {currency}")
            
            if balance < amount:
                logger.error(f"[{self.account_index}] Insufficient balance for withdrawal {balance} {currency} < {amount} {currency}")
                await self.exchange.close()
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking balance: {str(e)}")
            await self.exchange.close()
            raise

    async def get_eth_balance(self) -> Decimal:
        """Get ETH balance for the wallet address"""
        if self.web3 is None:
            raise ValueError(f"[{self.account_index}] Web3 instance not initialized. Network must be selected first.")

        balance_wei = self.web3.eth.get_balance(self.address)
        return Decimal(self.web3.from_wei(balance_wei, 'ether'))

    async def wait_for_balance_update(self, initial_balance: Decimal, timeout: int = 600) -> bool:
        """
        Wait for the balance to increase from the initial balance.
        Returns True if balance increased, False if timeout reached.
        """
        start_time = time.time()
        logger.info(f"[{self.account_index}] Waiting for funds to arrive. Initial balance: {initial_balance} ETH")
        
        while time.time() - start_time < timeout:
            try:
                current_balance = await self.get_eth_balance()
                if current_balance > initial_balance:
                    increase = current_balance - initial_balance
                    logger.success(f"[{self.account_index}] Funds received! Balance increased by {increase} ETH")
                    return True
                
                logger.info(f"[{self.account_index}] Current balance: {current_balance} ETH. Waiting...")
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"[{self.account_index}] Error checking balance: {str(e)}")
                await asyncio.sleep(5)
                
        logger.warning(f"[{self.account_index}] Timeout reached after {timeout} seconds. Funds not received.")
        return False

    async def withdraw(self) -> bool:
        """
        Withdraw from exchange to the specified address with retries.
        Returns True if withdrawal was successful and funds arrived.
        """
        try:
            if not self.config.EXCHANGES.withdrawals:
                raise ValueError("No withdrawal configurations found")
                
            withdrawal_config = self.config.EXCHANGES.withdrawals[0]
            if not withdrawal_config.networks:
                raise ValueError("No networks specified in withdrawal configuration")
                
            # Get chains info and validate withdrawal is enabled
            chains_info = await self.get_chains_info()
            if not chains_info:
                logger.error(f"[{self.account_index}] No available withdrawal networks found")
                return False
                
            currency = withdrawal_config.currency
            exchange_name = self.config.EXCHANGES.name.lower()
            
            # Get available enabled networks that match our config
            available_networks = []
            for network in withdrawal_config.networks:
                mapped_network = NETWORK_MAPPINGS[exchange_name].get(network)
                if not mapped_network:
                    continue
                    
                # Check if network exists and is enabled in chains_info
                for key, info in chains_info.items():
                    if key == mapped_network and info["withdrawEnabled"]:
                        available_networks.append((network, mapped_network, info))
                        break
                        
            if not available_networks:
                logger.error(f"[{self.account_index}] No enabled withdrawal networks found matching configuration")
                return False
                
            # Randomly select from available networks
            network, exchange_network, network_info = random.choice(available_networks)
            logger.info(f"[{self.account_index}] Selected network for withdrawal: {network} ({exchange_network})")
            
            # Update web3 instance with the correct RPC URL for the selected network
            self.network = network
            rpc_url = CEX_WITHDRAWAL_RPCS.get(self.network)
            if not rpc_url:
                logger.error(f"[{self.account_index}] No RPC URL found for network: {self.network}")
                return False
            self.web3 = Web3(Web3.HTTPProvider(rpc_url))
            # logger.info(f"[{self.account_index}] Updated web3 provider to: {rpc_url}")
            
            # Ensure withdrawal amount respects network minimum
            min_amount = max(withdrawal_config.min_amount, network_info["withdrawMin"])
            max_amount = withdrawal_config.max_amount
            
            if min_amount > max_amount:
                logger.error(f"[{self.account_index}] Network minimum ({network_info['withdrawMin']}) is higher than configured maximum ({max_amount})")
                await self.exchange.close()
                return False
                
            amount = round(random.uniform(min_amount, max_amount), random.randint(5, 12))
            
            # Check if we have enough balance for withdrawal
            if not await self.check_balance(amount):
                return False
                
            # Check if destination wallet balance exceeds maximum on ANY network
            # This prevents withdrawals if the wallet already has sufficient funds on any chain
            if not await self.check_all_networks_balance(withdrawal_config.max_balance):
                logger.warning(f"[{self.account_index}] Skipping withdrawal as destination wallet balance exceeds maximum on at least one network")
                await self.exchange.close()
                return False
             
            max_retries = withdrawal_config.retries
            
            for attempt in range(max_retries):
                try:
                    # Get initial balance before withdrawal
                    initial_balance = await self.get_eth_balance()
                    logger.info(f"[{self.account_index}] Attempting withdrawal {attempt + 1}/{max_retries}")
                    logger.info(f"[{self.account_index}] Withdrawing {amount} {currency} to {self.address}")
                    
                    # Get exchange-specific withdrawal parameters
                    params = {
                        'network': exchange_network,
                        'fee': network_info["withdrawFee"],
                        **EXCHANGE_PARAMS[exchange_name]["withdraw"]
                    }
                    
                    withdrawal = await self.exchange.withdraw(
                        currency,
                        amount,
                        self.address,
                        params=params
                    )
                    
                    logger.success(f"[{self.account_index}] Withdrawal initiated successfully")
                    
                    # Wait for funds to arrive if configured
                    if withdrawal_config.wait_for_funds:
                        funds_received = await self.wait_for_balance_update(
                            initial_balance,
                            timeout=withdrawal_config.max_wait_time
                        )
                        if funds_received:
                            await self.exchange.close()
                            return True
                        
                        logger.warning(f"[{self.account_index}] Funds not received yet, will retry withdrawal")
                    else:
                        await self.exchange.close()
                        return True  # If not waiting for funds, consider it successful
                    
                except ccxt.NetworkError as e:
                    if attempt == max_retries - 1:
                        logger.error(f"[{self.account_index}] Network error on final attempt: {str(e)}")
                        await self.exchange.close()
                        raise
                    logger.warning(f"[{self.account_index}] Network error, retrying: {str(e)}")
                    await asyncio.sleep(5)
                    
                except ccxt.ExchangeError as e:
                    error_msg = str(e).lower()
                    if "insufficient balance" in error_msg:
                        logger.error(f"[{self.account_index}] Insufficient balance in exchange account")
                        await self.exchange.close()
                        return False
                    if "whitelist" in error_msg or "not in withdraw whitelist" in error_msg:
                        logger.error(f"[{self.account_index}] Address not in whitelist: {str(e)}")
                        await self.exchange.close()
                        return False
                    if attempt == max_retries - 1:
                        logger.error(f"[{self.account_index}] Exchange error on final attempt: {str(e)}")
                        await self.exchange.close()
                        raise
                    logger.warning(f"[{self.account_index}] Exchange error, retrying: {str(e)}")
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logger.error(f"[{self.account_index}] Unexpected error during withdrawal: {str(e)}")
                    await self.exchange.close()
                    raise
                    
            logger.error(f"[{self.account_index}] Withdrawal failed after {max_retries} attempts")
            await self.exchange.close()
            return False
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Fatal error during withdrawal process: {str(e)}")
            await self.exchange.close()
            raise 

    async def check_all_networks_balance(self, max_balance: float) -> bool:
        """
        Check balances on all networks in the withdrawal configuration.
        Returns False if any network's balance exceeds the maximum allowed.
        """
        withdrawal_config = self.config.EXCHANGES.withdrawals[0]
        if not withdrawal_config.networks:
            raise ValueError("No networks specified in withdrawal configuration")
            
        # Store the current network and web3 instance to restore later
        original_network = self.network
        original_web3 = self.web3
        
        try:
            # Check balance on each network
            for network in withdrawal_config.networks:
                rpc_url = CEX_WITHDRAWAL_RPCS.get(network)
                if not rpc_url:
                    logger.warning(f"[{self.account_index}] No RPC URL found for network: {network}, skipping balance check")
                    continue
                    
                # Set up web3 for this network
                self.network = network
                self.web3 = Web3(Web3.HTTPProvider(rpc_url))
                
                try:
                    current_balance = await self.get_eth_balance()
                    if current_balance >= Decimal(str(max_balance)):
                        logger.warning(f"[{self.account_index}] Destination wallet balance on {network} ({current_balance}) exceeds maximum allowed ({max_balance})")
                        return False
                    logger.info(f"[{self.account_index}] Balance on {network}: {current_balance} ETH (below max: {max_balance})")
                except Exception as e:
                    logger.warning(f"[{self.account_index}] Error checking balance on {network}: {str(e)}")
                    
            return True
            
        finally:
            # Restore original network and web3 instance
            self.network = original_network
            self.web3 = original_web3 