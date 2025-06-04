GTE_SWAPS_CONTRACT = "0xA6b579684E943F7D00d616A48cF99b5147fC57A5"

GTE_TOKENS = {
    "WETH": {
        "address": "0x776401b9BC8aAe31A685731B7147D4445fD9FB19",
        "decimals": 18,
    },
    "GTE": {
        "address": "0x9629684df53db9E4484697D0A50C442B2BFa80A8",
        "decimals": 18,
    },
    "USDC":     {
        "address": "0x8d635c4702ba38b1f1735e8e784c7265dcc0b623",
        "decimals": 6,
        },
    "tkUSDC": {
        "address": "0xfaf334e157175ff676911adcf0964d7f54f2c424",
        "decimals": 6,
    },
    "MegaETH": {
        "address": "0x10a6be7d23989D00d528E68cF8051d095f741145",
        "decimals": 18,
    },
    "Kimchizuki": {
        "address": "0xA626F15D10F2b30AF1fb0d017F20a579500B5029",
        "decimals": 18,
    },
    "five": {
        "address": "0xF512886BC6877B0740E8Ca0B3c12bb4cA602B530",
        "decimals": 18,
    },
    "gte pepe": {
        "address": "0xBBA08CF5ECE0cC21e1DEB5168746c001B123A756",
        "decimals": 18,
    },
}

GTE_SWAPS_ABI = [
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "_factory",
                "type": "address"
            }, 
            {
                "internalType": "address",
                "name": "_WETH",
                "type": "address"
            }
        ],
        "stateMutability": "nonpayable",
        "type": "constructor"
    }, 
    {
        "inputs": [],
        "name": "WETH",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "tokenA",
            "type": "address"
        }, {
            "internalType": "address",
            "name": "tokenB",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "amountADesired",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountBDesired",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountAMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountBMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "addLiquidity",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountA",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountB",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "token",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "amountTokenDesired",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountTokenMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETHMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "addLiquidityETH",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountToken",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETH",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "factory",
        "outputs": [{
            "internalType": "address",
            "name": "",
            "type": "address"
        }],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveOut",
            "type": "uint256"
        }],
        "name": "getAmountIn",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveOut",
            "type": "uint256"
        }],
        "name": "getAmountOut",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }],
        "name": "getAmountsIn",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }],
        "name": "getAmountsOut",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountA",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveA",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "reserveB",
            "type": "uint256"
        }],
        "name": "quote",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountB",
            "type": "uint256"
        }],
        "stateMutability": "pure",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "tokenA",
            "type": "address"
        }, {
            "internalType": "address",
            "name": "tokenB",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountAMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountBMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "removeLiquidity",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountA",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountB",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "token",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountTokenMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETHMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "removeLiquidityETH",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountToken",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETH",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "token",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountTokenMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETHMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "removeLiquidityETHSupportingFeeOnTransferTokens",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountETH",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "token",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountTokenMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETHMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }, {
            "internalType": "bool",
            "name": "approveMax",
            "type": "bool"
        }, {
            "internalType": "uint8",
            "name": "v",
            "type": "uint8"
        }, {
            "internalType": "bytes32",
            "name": "r",
            "type": "bytes32"
        }, {
            "internalType": "bytes32",
            "name": "s",
            "type": "bytes32"
        }],
        "name": "removeLiquidityETHWithPermit",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountToken",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETH",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "token",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountTokenMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountETHMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }, {
            "internalType": "bool",
            "name": "approveMax",
            "type": "bool"
        }, {
            "internalType": "uint8",
            "name": "v",
            "type": "uint8"
        }, {
            "internalType": "bytes32",
            "name": "r",
            "type": "bytes32"
        }, {
            "internalType": "bytes32",
            "name": "s",
            "type": "bytes32"
        }],
        "name": "removeLiquidityETHWithPermitSupportingFeeOnTransferTokens",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountETH",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "address",
            "name": "tokenA",
            "type": "address"
        }, {
            "internalType": "address",
            "name": "tokenB",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "liquidity",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountAMin",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountBMin",
            "type": "uint256"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }, {
            "internalType": "bool",
            "name": "approveMax",
            "type": "bool"
        }, {
            "internalType": "uint8",
            "name": "v",
            "type": "uint8"
        }, {
            "internalType": "bytes32",
            "name": "r",
            "type": "bytes32"
        }, {
            "internalType": "bytes32",
            "name": "s",
            "type": "bytes32"
        }],
        "name": "removeLiquidityWithPermit",
        "outputs": [{
            "internalType": "uint256",
            "name": "amountA",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountB",
            "type": "uint256"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapETHForExactTokens",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactETHForTokens",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactETHForTokensSupportingFeeOnTransferTokens",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactTokensForETH",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactTokensForETHSupportingFeeOnTransferTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactTokensForTokens",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountIn",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountOutMin",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapExactTokensForTokensSupportingFeeOnTransferTokens",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountInMax",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapTokensForExactETH",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{
            "internalType": "uint256",
            "name": "amountOut",
            "type": "uint256"
        }, {
            "internalType": "uint256",
            "name": "amountInMax",
            "type": "uint256"
        }, {
            "internalType": "address[]",
            "name": "path",
            "type": "address[]"
        }, {
            "internalType": "address",
            "name": "to",
            "type": "address"
        }, {
            "internalType": "uint256",
            "name": "deadline",
            "type": "uint256"
        }],
        "name": "swapTokensForExactTokens",
        "outputs": [{
            "internalType": "uint256[]",
            "name": "amounts",
            "type": "uint256[]"
        }],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "stateMutability": "payable",
        "type": "receive"
    }
]