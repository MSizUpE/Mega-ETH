CEX_WITHDRAWAL_RPCS = {
    "Arbitrum": "https://arb1.lava.build",
    "Optimism": "https://optimism.lava.build",
    "Base": "https://base.lava.build",
}

# Network name mappings for different exchanges
NETWORK_MAPPINGS = {
    "okx": {
        "Arbitrum": "ARBONE",
        "Base": "Base",
        "Optimism": "OPTIMISM"
    },
    "bitget": {
        "Arbitrum": "ARBONE",
        "Base": "BASE",
        "Optimism": "OPTIMISM"
    }
}

# Exchange-specific parameters
EXCHANGE_PARAMS = {
    "okx": {
        "balance": {"type": "funding"},
        "withdraw": {"pwd": "-"}
    },
    "bitget": {
        "balance": {},
        "withdraw": {}
    }
}

# Supported exchanges
SUPPORTED_EXCHANGES = ["okx", "bitget"]