# MegaETH Bot 🌙

A powerful and flexible Ethereum Layer 2 automation tool with multiple features for MegaETH testnet activities.

---

## 🛠️ First Time Setup (Important)

Before your first run, **create or reset the task list database** using the built-in menu system.

It's very simple:

```
[3] 💾 Database actions  
[1] 🗑  Create/Reset Database  
[1] Yes  
[6] 👋 Exit  
[1] 🚀 Start farming  
```

---

## 🌟 Features
- ✨ Multi-threaded processing
- 🔄 Automatic retries with configurable attempts
- 🔐 Proxy support
- 📊 Account range selection
- 🎲 Random pauses between operations
- 🔔 Telegram logging integration
- 📝 Detailed transaction tracking
- 🧩 Modular task system

## 🎯 Available Actions:
- **Swaps**:
  - Bebop Exchange Trading
  - GTE Exchange Trading
- **Faucets**:
  - MegaETH Faucet
  - GTE Faucet
- **DeFi**:
  - Teko Finance Staking
- **Applications**:
  - Cap App (cUSD minting)
  - OnChain GM (NFT minting)
  - XL Meme (Meme token trading)

## 📋 Requirements
- Python 3.11 or higher
- Private keys for Ethereum wallets
- (Optional) Proxies for enhanced security
- Solvium API key for captcha solving
- (Optional) Telegram bot token for logging

## 🚀 Installation
1. Clone the repository:
```bash
git clone https://github.com/MSizUpE/Mega-ETH.git
cd Mega-ETH
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your settings in `config.yaml`
4. Add your private keys to `data/private_keys.txt`
5. (Optional) Add proxies to `data/proxies.txt`

## 📁 Project Structure
```
Mega-ETH/
├── data/
│   ├── private_keys.txt    # Ethereum wallet private keys
│   └── proxies.txt         # Proxy addresses (optional)
├── src/
│   ├── modules/            # Task-specific modules
│   └── utils/              # Helper utilities
├── config.yaml             # Main configuration file
└── tasks.py                # Task definitions
```

## 📝 Configuration

### 1. data files
- `private_keys.txt`: One private key per line
- `proxies.txt`: One proxy per line (format: `http://user:pass@ip:port`)

### 2. config.yaml Settings
```yaml
SETTINGS:
  THREADS: 1                      # Number of parallel threads
  ATTEMPTS: 5                     # Retry attempts for failed actions
  ACCOUNTS_RANGE: [0, 0]          # Wallet range to use (default: all)
  EXACT_ACCOUNTS_TO_USE: []       # Specific wallets to use (default: all)
  SHUFFLE_WALLETS: true           # Randomize wallet processing order
  PAUSE_BETWEEN_ATTEMPTS: [3, 10] # Random pause between retries
  PAUSE_BETWEEN_SWAPS: [5, 30]    # Random pause between swap operations
```

### 3. Module Configurations

**Swaps**:
```yaml
SWAPS:
  BEBOP:
    BALANCE_PERCENTAGE_TO_SWAP: [5, 10]  # Percentage range of balance to swap
    SWAP_ALL_TO_ETH: false               # Convert all tokens back to ETH

  GTE:
    BALANCE_PERCENTAGE_TO_SWAP: [5, 10]  # Percentage range of balance to swap
    SWAP_ALL_TO_ETH: true                # Convert all tokens back to ETH
    SWAPS_AMOUNT: [3, 5]                 # Number of swaps to perform
```

**Staking**:
```yaml
STAKINGS:
  TEKO_FINANCE:
    CHANCE_FOR_MINT_TOKENS: 50           # Probability of minting tokens
    BALANCE_PERCENTAGE_TO_STAKE: [5, 10] # Percentage range to stake
    UNSTAKE: false                       # Enable unstaking
```

**Minting**:
```yaml
MINTS:
  XL_MEME:
    BALANCE_PERCENTAGE_TO_BUY: [2, 5]    # Percentage of ETH to use for meme tokens
    CONTRACTS_TO_BUY: []                 # Specific token contracts to buy
```

## 🎮 Usage

### Task Configuration
Edit `tasks.py` to select which modules to run:

```python
TASKS = ["GTE_SWAPS"]  # Replace with your desired tasks
```

Available task presets:
- `FAUCET` - Claim MegaETH tokens (captcha required)
- `CAP_APP` - Mint cUSD
- `BEBOP` - Trade on Bebop exchange
- `GTE_SWAPS` - Trade on GTE exchange
- `TEKO_FINANCE` - Stake on Teko Finance platform
- `ONCHAIN_GM` - Mint GM NFTs
- `XL_MEME` - Buy meme tokens
- `GTE_FAUCET` - Claim tokens from GTE faucet

### Custom Task Sequences
You can create custom task sequences combining different modules:
```python
TASKS = ["MY_CUSTOM_TASK"]

MY_CUSTOM_TASK = [
    "faucet",                           # Run faucet first
    ("gte_swaps", "bebop"),             # Then run both in random order
    ["teko_finance", "xl_meme"],        # Then run only one randomly
]
```

### Run the bot:
```bash
python main.py
```

## 📜 License
MIT License

## ⚠️ Disclaimer 
This tool is for educational purposes only. Use at your own risk and in accordance with relevant terms of service.
