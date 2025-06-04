###
    SETTINGS:
###

THREADS: 1 – number of threads/simultaneous accounts the bot will run.

ATTEMPTS: 5 – how many times the bot will retry an action in case of an error.

ACCOUNTS_RANGE: [0, 0] – range of accounts to be processed.
Example: [3, 6] means the bot will process accounts from 3rd to 6th.

EXACT_ACCOUNTS_TO_USE: [] – *Works only if* ACCOUNTS_RANGE: [0, 0].
Example: [1, 3, 7] means the bot will only run accounts 1, 3, and 7.

SHUFFLE_WALLETS: false – whether to shuffle accounts before each run.
If true, accounts will be processed in random order every time.

PAUSE_BETWEEN_ATTEMPTS: [0, 0] – pause in seconds between retries of the same action.
Example: [3, 10] – pause will be random between 3 to 10 seconds.

PAUSE_BETWEEN_SWAPS: [0, 0] – pause in seconds between transaction submissions.
Example: [3, 10] – pause will be random between 3 to 10 seconds.

RANDOM_PAUSE_BETWEEN_ACCOUNTS: [0, 0] – pause in seconds between account processing.
Example: [3, 10] – pause will be random between 3 to 10 seconds.

RANDOM_PAUSE_BETWEEN_ACTIONS: [0, 0] – pause in seconds between tasks.
Example: [3, 10] – pause will be random between 3 to 10 seconds.

RANDOM_INITIALIZATION_PAUSE: [0, 0] – pause in seconds before starting each account.
Example: with 10 threads and [5, 60] – each account will wait 5 to 60 seconds before starting. 
Used to prevent all accounts from starting at once.

SEND_TELEGRAM_LOGS: false – whether to send function logs to Telegram or not. true/false.

TELEGRAM_BOT_TOKEN: "12317283:lskjalsdfasdfasd-sdfadfasd" – token of the Telegram bot created via @BotFather.

TELEGRAM_USERS_IDS: [235123432] – Telegram user IDs to send logs to.
NOTE! The bot only sends messages in direct chats, not in groups.
You can get your Telegram ID using @GetChatID_IL_BOT.

WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS: 120 – how many seconds to wait for transaction confirmation.

###
    FLOW
###
SKIP_FAILED_TASKS: false – whether to skip failed tasks or not.
If false, the bot will stop if any task fails.
If true, it will skip the task and continue with the next.

###
    RPCS
###
MEGAETH: ["https://carrot.megaeth.com/rpc"] – RPC for the network.
You can specify multiple; the bot will use one that works.

###
    OTHERS
###
SKIP_SSL_VERIFICATION: true – whether to skip SSL verification.
If you see SSL-related errors in the console, try setting this to false.

USE_PROXY_FOR_RPC: true – whether to use proxy for RPC.

###
    SWAPS
###

>>> BEBOP
BALANCE_PERCENTAGE_TO_SWAP: [5, 10] – what percentage of the balance to swap.
SWAP_ALL_TO_ETH: false – if true, bot will convert all tokens to ETH.

###
    STAKINGS
###

>>> EKO_FINANCE:
CHANCE_FOR_MINT_TOKENS: 0 – chance to mint test tokens.
100 means always mint 4 tokens.  
0 means no minting.  
Optimal: 50 for random minting chance.

BALANCE_PERCENTAGE_TO_STAKE: [5, 10] – what percentage of test tokens to deposit into staking.

UNSTAKE: true – whether to withdraw from staking.
If true, the bot will withdraw all funds from staking.

###
    MINTS
###

>>> XL_MEME:

Bot can only **buy** tokens, not sell them.

BALANCE_PERCENTAGE_TO_BUY: [10, 20] – ETH balance percentage to use for buying tokens.

CONTRACTS_TO_BUY: [] – list of token contracts to buy.
If empty, the bot will randomly fetch and buy contracts.