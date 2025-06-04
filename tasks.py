TASKS = ["FAUCET"]

FAUCET = ["faucet", "teko_faucet"]

CRUSTY_SWAP = [
    # "cex_withdrawal",
    "crusty_refuel",
    # "crusty_refuel_from_one_to_all",
]

CAP_APP = ["cap_app"]
BEBOP = ["bebop"]
GTE_SWAPS = ["gte_swaps"]
TEKO_FINANCE = ["teko_faucet", "teko_finance"]
ONCHAIN_GM = ["onchain_gm"]
XL_MEME = ["xl_meme"]
OMNIHUB = ["omnihub"]
MINTAIR = ["mintair"]
EASYNODE = ["easynode"]
HOPNETWORK = ["hopnetwork"]
OWLTO = ["owlto"]
RAINMAKR = ["rainmakr"]
RARIBLE = ["rarible"]
SUPERBOARD = ["superboard"]
CONFT_APP = ["conft_app"]
ZKCODEX = ["zkcodex"]
NERZO_MEGAETH = ["nerzo_megaeth"]
MORKIE_MEGA = ["morkie_mega"]
NERZO_FLUFFLE = ["nerzo_fluffle"]
"""
EN:
You can create your own task with the modules you need 
and add it to the TASKS list or use our ready-made preset tasks.

( ) - Means that all of the modules inside the brackets will be executed 
in random order
[ ] - Means that only one of the modules inside the brackets will be executed 
on random
SEE THE EXAMPLE BELOW:

RU:
Вы можете создать свою задачу с модулями, которые вам нужны, 
и добавить ее в список TASKS, см. пример ниже:

( ) - означает, что все модули внутри скобок будут выполнены в случайном порядке
[ ] - означает, что будет выполнен только один из модулей внутри скобок в случайном порядке
СМОТРИТЕ ПРИМЕР НИЖЕ:

CHINESE:
你可以创建自己的任务，使用你需要的模块，
并将其添加到TASKS列表中，请参见下面的示例：

( ) - 表示括号内的所有模块将按随机顺序执行
[ ] - 表示括号内的模块将按随机顺序执行

--------------------------------
!!! IMPORTANT !!!
EXAMPLE | ПРИМЕР | 示例:

TASKS = [
    "CREATE_YOUR_OWN_TASK",
]
CREATE_YOUR_OWN_TASK = [
    "faucet",
    ("faucet_tokens", "swaps"),
    ["storagescan_deploy", "conft_mint"],
    "swaps",
]
--------------------------------


BELOW ARE THE READY-MADE TASKS THAT YOU CAN USE:
СНИЗУ ПРИВЕДЕНЫ ГОТОВЫЕ ПРИМЕРЫ ЗАДАЧ, КОТОРЫЕ ВЫ МОЖЕТЕ ИСПОЛЬЗОВАТЬ:
以下是您可以使用的现成任务：


crusty_refuel - refuel MEGAETH at https://www.crustyswap.com/
crusty_refuel_from_one_to_all - refuel MEGAETH from one to all wallets at https://www.crustyswap.com/
cex_withdrawal - withdraw ETH from cex exchange (okx, bitget)
faucet - faucet mega eth tokens (needs captcha)
cap_app - mint cUSD at https://cap.app/testnet
bebop - trade tokens at https://bebop.xyz/trade?network=megaeth&sell=ETH
gte_swaps - trade tokens at https://testnet.gte.xyz/
teko_finance - stake tkUSDC at https://app.teko.finance/
onchain_gm - mint GM at https://onchaingm.com/
xl_meme - buy memetokens at https://testnet.xlmeme.com/megaeth
omnihub - mint NFT at https://omnihub.xyz/collections?chain=megaeth-testnet&sort_by=trending
mintair - deploy timer contract at https://contracts.mintair.xyz/
easynode - deploy counter contract at https://playground.easy-node.xyz/
hopnetwork - join waitlist at https://hopnetwork.xyz/
owlto - deploy basic contract at https://owlto.finance/deploy/?chain=MegaTestnet
rainmakr - buy meme token at https://rainmakr.xyz/en/rainai
rarible - mint NFT at https://testnet.rarible.fun/collections/megaethtestnet
superboard - complete quests at https://superboard.xyz/campaign/megaeth-testnet-real-time-era
conft_app - mint NFT and domain at https://conft.app/quests/6342 | Every mint costs 0.0013 ETH
zkcodex - deploys on https://zkcodex.com/onchain/deploy
nerzo_megaeth - mint megaeth at https://www.nerzo.xyz/megaeth
morkie_mega - mint megaeth at https://morkie.xyz/mega
nerzo_fluffle - mint fluffle at https://www.nerzo.xyz/fluffle
"""
