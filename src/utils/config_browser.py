import os
import yaml
import json
from flask import Flask, render_template, request, jsonify, send_from_directory
import webbrowser
import threading
import time
import logging
from flask.cli import show_server_banner
import traceback

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "config_interface", "static"),
    template_folder=os.path.join(
        os.path.dirname(__file__), "config_interface", "templates"
    ),
)

# Путь к файлу конфигурации
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")


# Добавьте обработчик ошибок для Flask
@app.errorhandler(Exception)
def handle_exception(e):
    """Обрабатывает все необработанные исключения"""
    # Записываем полный стек-трейс в лог
    logger.error(f"Unhandled exception: {str(e)}")
    logger.error(traceback.format_exc())
    return "Internal Server Error: Check logs for details", 500


def load_config():
    """Загрузка конфигурации из YAML файла"""
    try:
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        logger.info(f"Loading config from: {config_path}")

        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            return {}

        with open(config_path, "r") as file:
            config = yaml.safe_load(file)

            # Ensure all required sections exist
            required_sections = [
                "SETTINGS",
                "FLOW",
                "FAUCET",
                "RPCS",
                "OTHERS",
                "SWAPS",
                "STAKINGS",
                "MINTS",
                "DEPLOY",
                "EXCHANGES",
                "CRUSTY_SWAP",
            ]
            for section in required_sections:
                if section not in config:
                    config[section] = {}

            # Ensure SETTINGS has all required fields with default values
            if "SETTINGS" in config:
                defaults = {
                    "THREADS": 1,
                    "ATTEMPTS": 5,
                    "ACCOUNTS_RANGE": [0, 0],
                    "EXACT_ACCOUNTS_TO_USE": [],
                    "SHUFFLE_WALLETS": True,
                    "PAUSE_BETWEEN_ATTEMPTS": [3, 10],
                    "PAUSE_BETWEEN_SWAPS": [3, 10],
                    "RANDOM_PAUSE_BETWEEN_ACCOUNTS": [3, 10],
                    "RANDOM_PAUSE_BETWEEN_ACTIONS": [3, 10],
                    "RANDOM_INITIALIZATION_PAUSE": [5, 30],
                    "SEND_TELEGRAM_LOGS": False,
                    "TELEGRAM_BOT_TOKEN": "",
                    "TELEGRAM_USERS_IDS": [],
                    "WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS": 120,
                }

                for key, default_value in defaults.items():
                    if key not in config["SETTINGS"]:
                        config["SETTINGS"][key] = default_value

            # Ensure FLOW has all required fields
            if "FLOW" in config:
                flow_defaults = {"SKIP_FAILED_TASKS": False}

                for key, default_value in flow_defaults.items():
                    if key not in config["FLOW"]:
                        config["FLOW"][key] = default_value

            # Ensure FAUCET has all required fields
            if "FAUCET" in config:
                faucet_defaults = {
                    "SOLVIUM_API_KEY": "",
                    "USE_CAPSOLVER": False,
                    "CAPSOLVER_API_KEY": "",
                }

                for key, default_value in faucet_defaults.items():
                    if key not in config["FAUCET"]:
                        config["FAUCET"][key] = default_value

            # Ensure RPCS has MEGAETH field
            if "RPCS" in config:
                rpcs_defaults = {"MEGAETH": ["https://carrot.megaeth.com/rpc"]}

                for key, default_value in rpcs_defaults.items():
                    if key not in config["RPCS"]:
                        config["RPCS"][key] = default_value

            # Ensure OTHERS has required fields
            if "OTHERS" in config:
                others_defaults = {
                    "SKIP_SSL_VERIFICATION": True,
                    "USE_PROXY_FOR_RPC": True,
                }

                for key, default_value in others_defaults.items():
                    if key not in config["OTHERS"]:
                        config["OTHERS"][key] = default_value

            # Ensure SWAPS has required fields
            if "SWAPS" not in config:
                config["SWAPS"] = {}

            # Ensure BEBOP section exists in SWAPS
            if "BEBOP" not in config["SWAPS"]:
                config["SWAPS"]["BEBOP"] = {}

            bebop_defaults = {
                "BALANCE_PERCENTAGE_TO_SWAP": [5, 10],
                "SWAP_ALL_TO_ETH": False,
            }

            for key, default_value in bebop_defaults.items():
                if key not in config["SWAPS"]["BEBOP"]:
                    config["SWAPS"]["BEBOP"][key] = default_value

            # Ensure GTE section exists in SWAPS
            if "GTE" not in config["SWAPS"]:
                config["SWAPS"]["GTE"] = {}

            gte_defaults = {
                "BALANCE_PERCENTAGE_TO_SWAP": [5, 10],
                "SWAP_ALL_TO_ETH": True,
                "SWAPS_AMOUNT": [3, 5],
            }

            for key, default_value in gte_defaults.items():
                if key not in config["SWAPS"]["GTE"]:
                    config["SWAPS"]["GTE"][key] = default_value

            # Ensure STAKINGS has required fields
            if "STAKINGS" not in config:
                config["STAKINGS"] = {}

            # Ensure TEKO_FINANCE section exists in STAKINGS
            if "TEKO_FINANCE" not in config["STAKINGS"]:
                config["STAKINGS"]["TEKO_FINANCE"] = {}

            teko_finance_defaults = {
                "CHANCE_FOR_MINT_TOKENS": 50,
                "BALANCE_PERCENTAGE_TO_STAKE": [5, 10],
                "UNSTAKE": False,
            }

            for key, default_value in teko_finance_defaults.items():
                if key not in config["STAKINGS"]["TEKO_FINANCE"]:
                    config["STAKINGS"]["TEKO_FINANCE"][key] = default_value

            # Ensure MINTS has required fields
            if "MINTS" not in config:
                config["MINTS"] = {}

            # Ensure XL_MEME section exists in MINTS
            if "XL_MEME" not in config["MINTS"]:
                config["MINTS"]["XL_MEME"] = {}

            xl_meme_defaults = {
                "BALANCE_PERCENTAGE_TO_BUY": [2, 5],
                "CONTRACTS_TO_BUY": [],
            }

            for key, default_value in xl_meme_defaults.items():
                if key not in config["MINTS"]["XL_MEME"]:
                    config["MINTS"]["XL_MEME"][key] = default_value

            # Ensure RARIBLE section exists in MINTS
            if "RARIBLE" not in config["MINTS"]:
                config["MINTS"]["RARIBLE"] = {}

            rarible_defaults = {
                "CONTRACTS_TO_BUY": [],
            }

            for key, default_value in rarible_defaults.items():
                if key not in config["MINTS"]["RARIBLE"]:
                    config["MINTS"]["RARIBLE"][key] = default_value

            # Ensure OMNIHUB section exists in MINTS
            if "OMNIHUB" not in config["MINTS"]:
                config["MINTS"]["OMNIHUB"] = {}

            omnihub_defaults = {
                "MAX_PRICE_TO_MINT": 0.00011,
            }

            for key, default_value in omnihub_defaults.items():
                if key not in config["MINTS"]["OMNIHUB"]:
                    config["MINTS"]["OMNIHUB"][key] = default_value

            # Ensure RAINMAKR section exists in MINTS
            if "RAINMAKR" not in config["MINTS"]:
                config["MINTS"]["RAINMAKR"] = {}

            rainmakr_defaults = {
                "AMOUNT_OF_ETH_TO_BUY": [0.00013, 0.00015],
                "CONTRACTS_TO_BUY": [],
            }

            for key, default_value in rainmakr_defaults.items():
                if key not in config["MINTS"]["RAINMAKR"]:
                    config["MINTS"]["RAINMAKR"][key] = default_value

            # Ensure CRUSTY_SWAP has required fields
            if "CRUSTY_SWAP" not in config:
                config["CRUSTY_SWAP"] = {}

            crusty_swap_defaults = {
                "NETWORKS_TO_REFUEL_FROM": ["Arbitrum", "Optimism", "Base"],
                "AMOUNT_TO_REFUEL": [0.0001, 0.00015],
                "MINIMUM_BALANCE_TO_REFUEL": 99999,
                "WAIT_FOR_FUNDS_TO_ARRIVE": True,
                "MAX_WAIT_TIME": 999999,
                "BRIDGE_ALL": False,
                "BRIDGE_ALL_MAX_AMOUNT": 0.01,
            }

            for key, default_value in crusty_swap_defaults.items():
                if key not in config["CRUSTY_SWAP"]:
                    config["CRUSTY_SWAP"][key] = default_value

            # Ensure DEPLOY has required fields
            if "DEPLOY" not in config:
                config["DEPLOY"] = {}

            # Ensure ZKCODEX section exists in DEPLOY
            if "ZKCODEX" not in config["DEPLOY"]:
                config["DEPLOY"]["ZKCODEX"] = {}

            zkcodex_defaults = {
                "DEPLOY_TOKEN": True,
                "DEPLOY_NFT": True,
                "DEPLOY_CONTRACT": True,
                "ONE_ACTION_PER_LAUNCH": False,
            }

            for key, default_value in zkcodex_defaults.items():
                if key not in config["DEPLOY"]["ZKCODEX"]:
                    config["DEPLOY"]["ZKCODEX"][key] = default_value

            # Ensure EXCHANGES has required fields
            if "EXCHANGES" not in config:
                config["EXCHANGES"] = {}

            exchanges_defaults = {
                "name": "OKX",
                "apiKey": "",
                "secretKey": "",
                "passphrase": "",
                "withdrawals": [],
            }

            for key, default_value in exchanges_defaults.items():
                if key not in config["EXCHANGES"]:
                    config["EXCHANGES"][key] = default_value

            # Ensure withdrawals array exists and has at least one item with defaults
            if not config["EXCHANGES"]["withdrawals"]:
                config["EXCHANGES"]["withdrawals"] = [
                    {
                        "currency": "ETH",
                        "networks": ["Arbitrum", "Optimism"],
                        "min_amount": 0.0003,
                        "max_amount": 0.0004,
                        "max_balance": 0.005,
                        "wait_for_funds": True,
                        "max_wait_time": 99999,
                        "retries": 3,
                    }
                ]

            logger.info(f"Config loaded successfully")
            return config
    except Exception as e:
        logger.error(f"Error loading config: {str(e)}")
        logger.error(traceback.format_exc())
        return {}


def save_config(config):
    """Сохранение конфигурации в YAML файл"""
    try:
        # Проверяем наличие всех необходимых разделов
        required_sections = [
            "SETTINGS",
            "FLOW",
            "FAUCET",
            "RPCS",
            "OTHERS",
            "SWAPS",
            "STAKINGS",
            "MINTS",
            "DEPLOY",
            "EXCHANGES",
            "CRUSTY_SWAP",
        ]
        for section in required_sections:
            if section not in config:
                config[section] = {}

        # Убедимся, что раздел SETTINGS содержит все необходимые поля
        if "SETTINGS" in config:
            settings_defaults = {
                "THREADS": 1,
                "ATTEMPTS": 5,
                "ACCOUNTS_RANGE": [0, 0],
                "EXACT_ACCOUNTS_TO_USE": [],
                "SHUFFLE_WALLETS": True,
                "PAUSE_BETWEEN_ATTEMPTS": [3, 10],
                "PAUSE_BETWEEN_SWAPS": [3, 10],
                "RANDOM_PAUSE_BETWEEN_ACCOUNTS": [3, 10],
                "RANDOM_PAUSE_BETWEEN_ACTIONS": [3, 10],
                "RANDOM_INITIALIZATION_PAUSE": [5, 30],
                "SEND_TELEGRAM_LOGS": False,
                "TELEGRAM_BOT_TOKEN": "",
                "TELEGRAM_USERS_IDS": [],
                "WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS": 120,
            }
            for key, default_value in settings_defaults.items():
                if key not in config["SETTINGS"]:
                    config["SETTINGS"][key] = default_value

        # Убедимся, что раздел FLOW содержит все необходимые поля
        if "FLOW" in config:
            flow_defaults = {"SKIP_FAILED_TASKS": False}
            for key, default_value in flow_defaults.items():
                if key not in config["FLOW"]:
                    config["FLOW"][key] = default_value

        # Убедимся, что раздел FAUCET содержит все необходимые поля
        if "FAUCET" not in config:
            config["FAUCET"] = {}

        faucet_defaults = {
            "SOLVIUM_API_KEY": "",
            "USE_CAPSOLVER": False,
            "CAPSOLVER_API_KEY": "",
        }
        for key, default_value in faucet_defaults.items():
            if key not in config["FAUCET"]:
                config["FAUCET"][key] = default_value

        # Убедимся, что раздел RPCS содержит все необходимые поля
        if "RPCS" not in config:
            config["RPCS"] = {}

        rpcs_defaults = {"MEGAETH": ["https://carrot.megaeth.com/rpc"]}
        for key, default_value in rpcs_defaults.items():
            if key not in config["RPCS"]:
                config["RPCS"][key] = default_value

        # Убедимся, что раздел OTHERS содержит все необходимые поля
        if "OTHERS" not in config:
            config["OTHERS"] = {}

        others_defaults = {
            "SKIP_SSL_VERIFICATION": True,
            "USE_PROXY_FOR_RPC": True,
        }
        for key, default_value in others_defaults.items():
            if key not in config["OTHERS"]:
                config["OTHERS"][key] = default_value

        # Убедимся, что раздел SWAPS содержит все необходимые поля
        if "SWAPS" not in config:
            config["SWAPS"] = {}

        # Убедимся, что раздел BEBOP содержит все необходимые поля
        if "BEBOP" not in config["SWAPS"]:
            config["SWAPS"]["BEBOP"] = {}

        bebop_defaults = {
            "BALANCE_PERCENTAGE_TO_SWAP": [5, 10],
            "SWAP_ALL_TO_ETH": False,
        }
        for key, default_value in bebop_defaults.items():
            if key not in config["SWAPS"]["BEBOP"]:
                config["SWAPS"]["BEBOP"][key] = default_value

        # Убедимся, что раздел GTE содержит все необходимые поля
        if "GTE" not in config["SWAPS"]:
            config["SWAPS"]["GTE"] = {}

        gte_defaults = {
            "BALANCE_PERCENTAGE_TO_SWAP": [5, 10],
            "SWAP_ALL_TO_ETH": True,
            "SWAPS_AMOUNT": [3, 5],
        }
        for key, default_value in gte_defaults.items():
            if key not in config["SWAPS"]["GTE"]:
                config["SWAPS"]["GTE"][key] = default_value

        # Убедимся, что раздел STAKINGS содержит все необходимые поля
        if "STAKINGS" not in config:
            config["STAKINGS"] = {}

        # Убедимся, что раздел TEKO_FINANCE содержит все необходимые поля
        if "TEKO_FINANCE" not in config["STAKINGS"]:
            config["STAKINGS"]["TEKO_FINANCE"] = {}

        teko_finance_defaults = {
            "CHANCE_FOR_MINT_TOKENS": 50,
            "BALANCE_PERCENTAGE_TO_STAKE": [5, 10],
            "UNSTAKE": False,
        }
        for key, default_value in teko_finance_defaults.items():
            if key not in config["STAKINGS"]["TEKO_FINANCE"]:
                config["STAKINGS"]["TEKO_FINANCE"][key] = default_value

        # Убедимся, что раздел MINTS содержит все необходимые поля
        if "MINTS" not in config:
            config["MINTS"] = {}

        # Убедимся, что раздел XL_MEME содержит все необходимые поля
        if "XL_MEME" not in config["MINTS"]:
            config["MINTS"]["XL_MEME"] = {}

        xl_meme_defaults = {
            "BALANCE_PERCENTAGE_TO_BUY": [2, 5],
            "CONTRACTS_TO_BUY": [],
        }
        for key, default_value in xl_meme_defaults.items():
            if key not in config["MINTS"]["XL_MEME"]:
                config["MINTS"]["XL_MEME"][key] = default_value

        # Убедимся, что раздел RARIBLE содержит все необходимые поля
        if "RARIBLE" not in config["MINTS"]:
            config["MINTS"]["RARIBLE"] = {}

        rarible_defaults = {
            "CONTRACTS_TO_BUY": [],
        }
        for key, default_value in rarible_defaults.items():
            if key not in config["MINTS"]["RARIBLE"]:
                config["MINTS"]["RARIBLE"][key] = default_value

        # Убедимся, что раздел OMNIHUB содержит все необходимые поля
        if "OMNIHUB" not in config["MINTS"]:
            config["MINTS"]["OMNIHUB"] = {}

        omnihub_defaults = {
            "MAX_PRICE_TO_MINT": 0.00011,
        }
        for key, default_value in omnihub_defaults.items():
            if key not in config["MINTS"]["OMNIHUB"]:
                config["MINTS"]["OMNIHUB"][key] = default_value

        # Убедимся, что раздел RAINMAKR содержит все необходимые поля
        if "RAINMAKR" not in config["MINTS"]:
            config["MINTS"]["RAINMAKR"] = {}

        rainmakr_defaults = {
            "AMOUNT_OF_ETH_TO_BUY": [0.00013, 0.00015],
            "CONTRACTS_TO_BUY": [],
        }
        for key, default_value in rainmakr_defaults.items():
            if key not in config["MINTS"]["RAINMAKR"]:
                config["MINTS"]["RAINMAKR"][key] = default_value

        # Убедимся, что раздел CRUSTY_SWAP содержит все необходимые поля
        if "CRUSTY_SWAP" not in config:
            config["CRUSTY_SWAP"] = {}

        crusty_swap_defaults = {
            "NETWORKS_TO_REFUEL_FROM": ["Arbitrum", "Optimism", "Base"],
            "AMOUNT_TO_REFUEL": [0.0001, 0.00015],
            "MINIMUM_BALANCE_TO_REFUEL": 99999,
            "WAIT_FOR_FUNDS_TO_ARRIVE": True,
            "MAX_WAIT_TIME": 999999,
            "BRIDGE_ALL": False,
            "BRIDGE_ALL_MAX_AMOUNT": 0.01,
        }
        for key, default_value in crusty_swap_defaults.items():
            if key not in config["CRUSTY_SWAP"]:
                config["CRUSTY_SWAP"][key] = default_value

        # Убедимся, что раздел DEPLOY содержит все необходимые поля
        if "DEPLOY" not in config:
            config["DEPLOY"] = {}

        # Убедимся, что раздел ZKCODEX содержит все необходимые поля
        if "ZKCODEX" not in config["DEPLOY"]:
            config["DEPLOY"]["ZKCODEX"] = {}

        zkcodex_defaults = {
            "DEPLOY_TOKEN": True,
            "DEPLOY_NFT": True,
            "DEPLOY_CONTRACT": True,
            "ONE_ACTION_PER_LAUNCH": False,
        }
        for key, default_value in zkcodex_defaults.items():
            if key not in config["DEPLOY"]["ZKCODEX"]:
                config["DEPLOY"]["ZKCODEX"][key] = default_value

        # Убедимся, что раздел EXCHANGES содержит все необходимые поля
        if "EXCHANGES" not in config:
            config["EXCHANGES"] = {}

        exchanges_defaults = {
            "name": "OKX",
            "apiKey": "",
            "secretKey": "",
            "passphrase": "",
            "withdrawals": [],
        }
        for key, default_value in exchanges_defaults.items():
            if key not in config["EXCHANGES"]:
                config["EXCHANGES"][key] = default_value

        # Убедимся, что массив withdrawals существует и содержит хотя бы один элемент с дефолтными значениями
        if not config["EXCHANGES"]["withdrawals"]:
            config["EXCHANGES"]["withdrawals"] = [
                {
                    "currency": "ETH",
                    "networks": ["Arbitrum", "Optimism"],
                    "min_amount": 0.0003,
                    "max_amount": 0.0004,
                    "max_balance": 0.005,
                    "wait_for_funds": True,
                    "max_wait_time": 99999,
                    "retries": 3,
                }
            ]

        with open(CONFIG_PATH, "w") as file:
            yaml.dump(config, file, default_flow_style=False, sort_keys=False)

        logger.info(f"Configuration saved to {CONFIG_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {str(e)}")
        logger.error(traceback.format_exc())
        return False


@app.route("/")
def index():
    """Главная страница с интерфейсом конфигурации"""
    try:
        # Проверяем наличие шаблона перед рендерингом
        template_path = os.path.join(
            os.path.dirname(__file__), "config_interface", "templates", "config.html"
        )
        if not os.path.exists(template_path):
            logger.error(f"Template not found: {template_path}")
            return "Template not found. Please check logs for details."

        return render_template("config.html")
    except Exception as e:
        logger.error(f"Error rendering template: {str(e)}")
        logger.error(traceback.format_exc())
        return f"Error: {str(e)}"


@app.route("/api/config", methods=["GET"])
def get_config():
    """API для получения текущей конфигурации"""
    config = load_config()
    return jsonify(config)


@app.route("/api/config", methods=["POST"])
def update_config():
    """API для обновления конфигурации"""
    try:
        new_config = request.get_json()
        logger.info(f"Saving new configuration: {json.dumps(new_config, indent=2)}")
        save_config(new_config)
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Error saving config: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


def open_browser():
    """Открывает браузер после запуска сервера"""
    time.sleep(2)  # Даем серверу время на запуск
    try:
        webbrowser.open(f"http://127.0.0.1:3456")
        logger.info("Browser opened successfully")
    except Exception as e:
        logger.error(f"Failed to open browser: {str(e)}")


def create_required_directories():
    """Создает необходимые директории для шаблонов и статических файлов"""
    try:
        # Изменяем пути для сохранения файлов
        base_dir = os.path.join(os.path.dirname(__file__), "config_interface")
        template_dir = os.path.join(base_dir, "templates")
        static_dir = os.path.join(base_dir, "static")
        css_dir = os.path.join(static_dir, "css")
        js_dir = os.path.join(static_dir, "js")

        # Создаем все необходимые директории
        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(css_dir, exist_ok=True)
        os.makedirs(js_dir, exist_ok=True)

        # Создаем HTML шаблон
        html_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuration</title>
    <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700&family=Roboto:wght@300;400;500;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="background-shapes">
        <div class="shape shape-1"></div>
        <div class="shape shape-2"></div>
        <div class="shape shape-3"></div>
        <div class="shape shape-4"></div>
        <div class="shape shape-5"></div>
        <div class="shape shape-6"></div>
    </div>
    
    <div class="app-container">
        <header>
            <div class="logo">
                <i class="fas fa-star"></i>
                <h1>MegaETH Configuration</h1>
            </div>
            <div class="header-controls">
                <button id="saveButton" class="btn save-btn"><i class="fas fa-save"></i> Save Configuration</button>
            </div>
        </header>
        
        <main>
            <div class="sidebar">
                <div class="sidebar-menu">
                    <div class="sidebar-item active" data-section="settings">
                        <i class="fas fa-cog"></i>
                        <span>Settings</span>
                    </div>
                    <div class="sidebar-item" data-section="flow">
                        <i class="fas fa-exchange-alt"></i>
                        <span>Flow</span>
                    </div>
                    <div class="sidebar-item" data-section="faucet">
                        <i class="fas fa-robot"></i>
                        <span>Faucet & Captcha</span>
                    </div>
                    <div class="sidebar-item" data-section="rpcs">
                        <i class="fas fa-network-wired"></i>
                        <span>RPCs</span>
                    </div>
                    <div class="sidebar-item" data-section="others">
                        <i class="fas fa-ellipsis-h"></i>
                        <span>Others</span>
                    </div>
                    <div class="sidebar-item" data-section="swaps">
                        <i class="fas fa-sync-alt"></i>
                        <span>Swaps</span>
                    </div>
                    <div class="sidebar-item" data-section="stakings">
                        <i class="fas fa-coins"></i>
                        <span>Stakings</span>
                    </div>
                    <div class="sidebar-item" data-section="mints">
                        <i class="fas fa-hammer"></i>
                        <span>Mints</span>
                    </div>
                    <div class="sidebar-item" data-section="crustyswap">
                        <i class="fas fa-network-wired"></i>
                        <span>Crusty Swap</span>
                    </div>
                    <div class="sidebar-item" data-section="exchanges">
                        <i class="fas fa-exchange-alt"></i>
                        <span>Exchanges</span>
                    </div>
                </div>
            </div>
            
            <div class="content">
                <div id="configContainer">
                    <!-- Здесь будут динамически созданные элементы конфигурации -->
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Loading configuration...</p>
                    </div>
                </div>
            </div>
        </main>
        
        <footer>
            <div class="system-status">
                <span class="status-indicator online"></span>
                System ready
            </div>
            <div class="version">v1.0.0</div>
        </footer>
    </div>
    
    <!-- Модальное окно для уведомлений -->
    <div id="notification" class="notification">
        <div class="notification-content">
            <i class="fas fa-check-circle notification-icon success"></i>
            <i class="fas fa-exclamation-circle notification-icon error"></i>
            <p id="notification-message"></p>
        </div>
    </div>
    
    <script src="{{ url_for('static', filename='js/config.js') }}"></script>
</body>
</html>
"""

        # Создаем CSS файл с улучшенным дизайном
        css_content = """:root {
    /* Основные цвета */
    --primary-blue: #3A86FF;      /* Основной синий */
    --secondary-blue: #4361EE;    /* Вторичный синий */
    --dark-blue: #2B4EFF;         /* Темно-синий */
    --light-blue: #60A5FA;        /* Светло-синий */
    
    /* Неоновые акценты (приглушенные) */
    --neon-blue: #4895EF;         /* Неоновый синий */
    --neon-purple: #8B5CF6;       /* Неоновый фиолетовый */
    --neon-pink: #EC4899;         /* Неоновый розовый (приглушенный) */
    --neon-cyan: #22D3EE;         /* Неоновый голубой */
    
    /* Статусы */
    --success: #10B981;           /* Зеленый */
    --error: #EF4444;             /* Красный */
    --warning: #F59E0B;           /* Оранжевый */
    --info: #3B82F6;              /* Синий */
    
    /* Фоны */
    --bg-dark: #1A1A2E;           /* Темно-синий фон */
    --bg-card: rgba(26, 26, 46, 0.6); /* Полупрозрачный фон карточек */
    --bg-card-hover: rgba(26, 26, 46, 0.8); /* Фон карточек при наведении */
    
    /* Текст */
    --text-primary: #F8FAFC;      /* Основной текст */
    --text-secondary: #94A3B8;    /* Вторичный текст */
    
    /* Тени */
    --shadow-sm: 0 2px 10px rgba(0, 0, 0, 0.1);
    --shadow-md: 0 4px 20px rgba(0, 0, 0, 0.15);
    --shadow-lg: 0 10px 30px rgba(0, 0, 0, 0.2);
    
    /* Градиенты */
    --gradient-blue: linear-gradient(135deg, var(--primary-blue), var(--dark-blue));
    --gradient-purple-blue: linear-gradient(135deg, var(--neon-purple), var(--neon-blue));
    --gradient-blue-cyan: linear-gradient(135deg, var(--neon-blue), var(--neon-cyan));
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Poppins', sans-serif;
    background: var(--bg-dark);
    color: var(--text-primary);
    line-height: 1.6;
    min-height: 100vh;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 20px;
    position: relative;
    overflow-x: hidden;
    background: linear-gradient(135deg, #6A11CB, #FC2D7F, #FF9800);
}

/* Фоновые формы */
.background-shapes {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: -1;
    overflow: hidden;
}

.shape {
    position: absolute;
    border-radius: 50%;
    filter: blur(40px);
    opacity: 0.4;
}

.shape-1 {
    top: 10%;
    left: 10%;
    width: 300px;
    height: 300px;
    background: var(--neon-purple);
    animation: float 15s infinite alternate;
}

.shape-2 {
    top: 60%;
    left: 20%;
    width: 200px;
    height: 200px;
    background: var(--neon-blue);
    animation: float 12s infinite alternate-reverse;
}

.shape-3 {
    top: 20%;
    right: 15%;
    width: 250px;
    height: 250px;
    background: var(--neon-pink);
    animation: float 18s infinite alternate;
}

.shape-4 {
    bottom: 15%;
    right: 10%;
    width: 180px;
    height: 180px;
    background: var(--neon-cyan);
    animation: float 10s infinite alternate-reverse;
}

.shape-5 {
    top: 40%;
    left: 50%;
    width: 150px;
    height: 150px;
    background: var(--primary-blue);
    animation: float 14s infinite alternate;
}

.shape-6 {
    bottom: 30%;
    left: 30%;
    width: 120px;
    height: 120px;
    background: var(--secondary-blue);
    animation: float 16s infinite alternate-reverse;
}

@keyframes float {
    0% {
        transform: translate(0, 0) scale(1);
    }
    100% {
        transform: translate(30px, 30px) scale(1.1);
    }
}

.app-container {
    width: 90%;
    max-width: 1400px;
    background: rgba(26, 26, 46, 0.7);
    backdrop-filter: blur(20px);
    border-radius: 20px;
    overflow: hidden;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.3);
    display: flex;
    flex-direction: column;
    border: 1px solid rgba(255, 255, 255, 0.1);
    position: relative;
    z-index: 1;
    height: 90vh;
}

/* Заголовок */
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px 30px;
    background: rgba(26, 26, 46, 0.8);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    position: relative;
}

header::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    width: 100%;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent, 
        var(--neon-blue), 
        var(--primary-blue), 
        var(--neon-blue), 
        transparent
    );
    opacity: 0.6;
}

.logo {
    display: flex;
    align-items: center;
    gap: 12px;
}

.logo i {
    font-size: 28px;
    color: var(--neon-blue);
    text-shadow: 0 0 10px rgba(72, 149, 239, 0.5);
}

.logo h1 {
    font-size: 28px;
    font-weight: 600;
    color: var(--text-primary);
    position: relative;
}

.header-controls {
    display: flex;
    align-items: center;
    gap: 15px;
}

.btn {
    padding: 10px 20px;
    border-radius: 12px;
    border: none;
    background: rgba(58, 134, 255, 0.15);
    color: var(--text-primary);
    font-size: 16px;
    font-weight: 500;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    transition: all 0.3s ease;
}

.btn:hover {
    background: rgba(58, 134, 255, 0.25);
    transform: translateY(-2px);
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
}

.save-btn {
    background: var(--gradient-blue);
    padding: 12px 30px;
    font-size: 18px;
    font-weight: 600;
    min-width: 220px;
}

.save-btn:hover {
    box-shadow: 0 5px 15px rgba(58, 134, 255, 0.3);
}

/* Основной контент */
main {
    flex: 1;
    display: flex;
    overflow: hidden;
}

/* Боковое меню */
.sidebar {
    width: 250px;
    background: rgba(26, 26, 46, 0.8);
    border-right: 1px solid rgba(255, 255, 255, 0.1);
    padding: 20px 0;
    overflow-y: auto;
}

.sidebar-menu {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.sidebar-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 20px;
    cursor: pointer;
    transition: all 0.3s ease;
    border-radius: 8px;
    margin: 0 10px;
}

.sidebar-item:hover {
    background: rgba(58, 134, 255, 0.1);
}

.sidebar-item.active {
    background: rgba(58, 134, 255, 0.2);
    color: var(--neon-blue);
}

.sidebar-item i {
    font-size: 20px;
    width: 24px;
    text-align: center;
}

.sidebar-item span {
    font-size: 16px;
    font-weight: 500;
}

/* Основной контент */
.content {
    flex: 1;
    padding: 30px;
    overflow-y: auto;
}

/* Секции конфигурации */
.config-section {
    display: none;
    animation: fadeIn 0.3s ease;
}

.config-section.active {
    display: block;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.section-title {
    font-size: 24px;
    font-weight: 600;
    color: var(--neon-blue);
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

/* Карточки настроек */
.config-cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}

.config-card {
    background: var(--bg-card);
    backdrop-filter: blur(10px);
    border-radius: 16px;
    padding: 20px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: var(--shadow-md);
    transition: all 0.3s ease;
}

.config-card:hover {
    transform: translateY(-5px);
    box-shadow: var(--shadow-lg);
    background: var(--bg-card-hover);
}

.card-title {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.card-title i {
    color: var(--neon-blue);
    font-size: 20px;
}

/* Поля ввода */
.config-field {
    margin-bottom: 20px;
}

.field-label {
    font-size: 16px;
    color: var(--text-primary);
    margin-bottom: 10px;
    display: block;
    font-weight: 500;
}

.field-input {
    background: rgba(26, 26, 46, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 12px 15px;
    color: var(--text-primary);
    font-size: 16px;
    width: 100%;
    transition: all 0.3s ease;
    font-weight: 500;
}

.field-input:focus {
    outline: none;
    border-color: var(--neon-blue);
    box-shadow: 0 0 0 2px rgba(72, 149, 239, 0.2);
}

.range-input {
    display: flex;
    gap: 10px;
    align-items: center;
}

.range-input input {
    flex: 1;
    text-align: center;
    font-weight: 600;
}

.range-separator {
    color: var(--text-primary);
    font-weight: 600;
    font-size: 18px;
}

/* Чекбоксы */
.checkbox-field {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 20px;
    cursor: pointer;
}

.checkbox-input {
    appearance: none;
    width: 24px;
    height: 24px;
    background: rgba(26, 26, 46, 0.5);
    border: 2px solid rgba(255, 255, 255, 0.2);
    border-radius: 6px;
    position: relative;
    cursor: pointer;
    transition: all 0.3s ease;
}

.checkbox-input:checked {
    background: var(--neon-blue);
    border-color: var(--neon-blue);
}

.checkbox-input:checked::after {
    content: '✓';
    position: absolute;
    color: white;
    font-size: 16px;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
}

.checkbox-label {
    font-size: 16px;
    color: var(--text-primary);
    cursor: pointer;
    font-weight: 500;
}

/* Списки */
.list-field {
    position: relative;
}

.list-container {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 10px;
}

.list-item {
    background: rgba(58, 134, 255, 0.2);
    border-radius: 8px;
    padding: 6px 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}

.list-item span {
    font-size: 14px;
    color: var(--text-primary);
}

.list-item button {
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    opacity: 0.7;
    transition: opacity 0.3s;
}

.list-item button:hover {
    opacity: 1;
}

.add-list-item {
    display: flex;
    align-items: center;
    margin-top: 10px;
}

.add-list-item input {
    flex: 1;
    background: rgba(26, 26, 46, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px 0 0 12px;
    padding: 10px 15px;
    color: var(--text-primary);
    font-size: 14px;
}

.add-list-item button {
    background: var(--neon-blue);
    border: none;
    border-radius: 0 12px 12px 0;
    padding: 10px 15px;
    color: white;
    cursor: pointer;
    transition: background 0.3s;
}

.add-list-item button:hover {
    background: var(--dark-blue);
}

/* Футер */
footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 30px;
    background: rgba(26, 26, 46, 0.8);
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 14px;
    color: var(--text-secondary);
    position: relative;
}

footer::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 1px;
    background: linear-gradient(90deg, 
        transparent, 
        var(--neon-blue), 
        var(--primary-blue), 
        var(--neon-blue), 
        transparent
    );
    opacity: 0.6;
}

.system-status {
    display: flex;
    align-items: center;
    gap: 8px;
}

.status-indicator {
    width: 10px;
    height: 10px;
    border-radius: 50%;
}

.status-indicator.online {
    background: var(--success);
    box-shadow: 0 0 8px var(--success);
    animation: pulse 2s infinite;
    opacity: 0.9;
}

@keyframes pulse {
    0% { opacity: 0.6; }
    50% { opacity: 0.9; }
    100% { opacity: 0.6; }
}

.version {
    font-size: 14px;
}

/* Загрузка */
.loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    gap: 20px;
}

.spinner {
    width: 60px;
    height: 60px;
    border: 5px solid rgba(72, 149, 239, 0.2);
    border-radius: 50%;
    border-top-color: var(--neon-blue);
    animation: spin 1s linear infinite;
}

@keyframes spin {
    0% { transform: rotate(0deg); }
    100% { transform: rotate(360deg); }
}

/* Уведомления */
.notification {
    position: fixed;
    top: 20px;
    right: 20px;
    background: rgba(26, 26, 46, 0.9);
    backdrop-filter: blur(10px);
    border-radius: 12px;
    padding: 15px 20px;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
    transform: translateX(150%);
    transition: transform 0.3s ease;
    z-index: 1000;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.notification.show {
    transform: translateX(0);
}

.notification-content {
    display: flex;
    align-items: center;
    gap: 15px;
}

.notification-icon {
    font-size: 28px;
    display: none;
}

.notification-icon.success {
    color: var(--success);
}

.notification-icon.error {
    color: var(--error);
}

.notification.success .notification-icon.success {
    display: block;
}

.notification.error .notification-icon.error {
    display: block;
}

#notification-message {
    color: var(--text-primary);
    font-size: 16px;
    font-weight: 500;
}

/* Адаптивность */
@media (max-width: 1024px) {
    .config-cards {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 768px) {
    .app-container {
        width: 100%;
        height: 100vh;
        border-radius: 0;
    }
    
    header, footer {
        padding: 15px;
    }
    
    main {
        flex-direction: column;
    }
    
    .sidebar {
        width: 100%;
        border-right: none;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding: 10px 0;
    }
    
    .sidebar-menu {
        flex-direction: row;
        overflow-x: auto;
        padding: 0 10px;
    }
    
    .sidebar-item {
        padding: 10px 15px;
        white-space: nowrap;
    }
    
    .content {
        padding: 15px;
    }
}

/* Скроллбар */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: rgba(26, 26, 46, 0.3);
}

::-webkit-scrollbar-thumb {
    background: rgba(72, 149, 239, 0.5);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: rgba(72, 149, 239, 0.7);
}

/* Стилизация для маленьких числовых полей */
.small-input {
    max-width: 100px;
    text-align: center;
}

/* Стилизация для средних полей */
.medium-input {
    max-width: 200px;
}

/* Подсказки */
.tooltip {
    position: relative;
    display: inline-block;
    margin-left: 5px;
    color: var(--neon-blue);
    cursor: pointer;
}

.tooltip .tooltip-text {
    visibility: hidden;
    width: 200px;
    background: rgba(26, 26, 46, 0.95);
    color: var(--text-primary);
    text-align: center;
    border-radius: 8px;
    padding: 10px;
    position: absolute;
    z-index: 1;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%);
    opacity: 0;
    transition: opacity 0.3s;
    font-size: 14px;
    font-weight: normal;
    box-shadow: var(--shadow-md);
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.tooltip:hover .tooltip-text {
    visibility: visible;
    opacity: 1;
}

/* Стили для списков с тегами */
.tags-input {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    padding: 8px;
    background: rgba(26, 26, 46, 0.5);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    min-height: 50px;
}

.tag {
    display: flex;
    align-items: center;
    background: rgba(58, 134, 255, 0.2);
    padding: 5px 10px;
    border-radius: 6px;
    gap: 8px;
}

.tag-text {
    font-size: 14px;
    color: var(--text-primary);
}

.tag-remove {
    background: none;
    border: none;
    color: var(--text-primary);
    cursor: pointer;
    font-size: 14px;
    opacity: 0.7;
    transition: opacity 0.3s;
}

.tag-remove:hover {
    opacity: 1;
}

.tags-input input {
    flex: 1;
    min-width: 60px;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-size: 14px;
    padding: 5px;
}

.tags-input input::placeholder {
    color: var(--text-secondary);
    opacity: 0.7;
}
"""

        # Создаем JavaScript файл с улучшенной логикой
        js_content = """document.addEventListener('DOMContentLoaded', function() {
    // Загружаем конфигурацию при загрузке страницы
    fetchConfig();
    
    // Обработчик для кнопки сохранения
    document.getElementById('saveButton').addEventListener('click', saveConfig);
    
    // Обработчики для пунктов меню
    document.querySelectorAll('.sidebar-item').forEach(item => {
        item.addEventListener('click', function() {
            // Убираем активный класс у всех пунктов
            document.querySelectorAll('.sidebar-item').forEach(i => i.classList.remove('active'));
            // Добавляем активный класс текущему пункту
            this.classList.add('active');
            
            // Показываем соответствующую секцию
            const section = this.dataset.section;
            document.querySelectorAll('.config-section').forEach(s => s.classList.remove('active'));
            document.getElementById(`${section}-section`).classList.add('active');
        });
    });
});

// Функция для форматирования названий полей
function formatFieldName(name) {
    // Заменяем подчеркивания на пробелы
    let formatted = name.replace(/_/g, ' ');
    
    // Делаем первую букву заглавной, остальные строчными
    return formatted.charAt(0).toUpperCase() + formatted.slice(1).toLowerCase();
}

// Функция для загрузки конфигурации с сервера
async function fetchConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        renderConfig(config);
    } catch (error) {
        showNotification('Failed to load configuration: ' + error.message, 'error');
    }
}

// Функция для сохранения конфигурации
async function saveConfig() {
    try {
        const config = collectFormData();
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification('Configuration saved successfully!', 'success');
        } else {
            showNotification('Error: ' + result.message, 'error');
        }
    } catch (error) {
        showNotification('Failed to save configuration: ' + error.message, 'error');
    }
}

// Функция для сбора данных формы
function collectFormData() {
    config = {}
    
    // Собираем данные из всех полей ввода
    document.querySelectorAll('[data-config-path]').forEach(element => {
        const path = element.dataset.configPath.split('.');
        let current = config;
        
        // Check if this is a withdrawal field (has pattern like EXCHANGES.withdrawals[0].field)
        const isWithdrawalField = path.length >= 2 && path[1].includes('withdrawals[');
        
        // For regular fields
        if (!isWithdrawalField) {
            // Создаем вложенные объекты по пути
            for (let i = 0; i < path.length - 1; i++) {
                if (!current[path[i]]) {
                    current[path[i]] = {};
                }
                current = current[path[i]];
            }
        } 
        // For withdrawal fields
        else {
            // Ensure EXCHANGES exists
            if (!current['EXCHANGES']) {
                current['EXCHANGES'] = {};
            }
            
            // Ensure withdrawals array exists
            if (!current['EXCHANGES']['withdrawals']) {
                current['EXCHANGES']['withdrawals'] = [{}];
            }
            
            // Extract the index from the pattern withdrawals[X]
            const withdrawalIndexMatch = path[1].match(/withdrawals\[(\d+)\]/);
            const withdrawalIndex = withdrawalIndexMatch ? parseInt(withdrawalIndexMatch[1]) : 0;
            
            // Ensure the particular withdrawal object exists
            if (!current['EXCHANGES']['withdrawals'][withdrawalIndex]) {
                current['EXCHANGES']['withdrawals'][withdrawalIndex] = {};
            }
            
            current = current['EXCHANGES']['withdrawals'][withdrawalIndex];
            // Last part of the path for withdrawals is the actual field
            path[1] = path[path.length - 1]; 
            path.length = 2;
        }
        
        const lastKey = path[path.length - 1];
        
        if (element.type === 'checkbox') {
            current[lastKey] = element.checked;
        } else if (element.classList.contains('tags-input')) {
            // Обработка полей с тегами
            const tags = Array.from(element.querySelectorAll('.tag-text'))
                .map(tag => tag.textContent.trim());
            current[lastKey] = tags;
        } else if (element.classList.contains('range-min')) {
            const rangeKey = lastKey.replace('_MIN', '');
            if (!current[rangeKey]) {
                current[rangeKey] = [0, 0];
            }
            current[rangeKey][0] = parseInt(element.value, 10);

            // Check if this is a float type field
            if (element.dataset.type === 'float') {
                current[rangeKey][0] = parseFloat(element.value);
            } else {
                current[rangeKey][0] = parseInt(element.value, 10);
            }
        } else if (element.classList.contains('range-max')) {
            const rangeKey = lastKey.replace('_MAX', '');
            if (!current[rangeKey]) {
                current[rangeKey] = [0, 0];
            }
            current[rangeKey][1] = parseInt(element.value, 10);

            // Check if this is a float type field
            if (element.dataset.type === 'float') {
                current[rangeKey][1] = parseFloat(element.value);
            } else {
                current[rangeKey][1] = parseInt(element.value, 10);
            }
        } else if (element.classList.contains('list-input')) {
            // Для списков (разделенных запятыми)
            const items = element.value.split(',')
                .map(item => item.trim())
                .filter(item => item !== '');
                
            // Преобразуем в числа, если это числовой список
            if (element.dataset.type === 'number-list') {
                current[lastKey] = items.map(item => parseInt(item, 10));
            } else {
                current[lastKey] = items;
            }
        } else {
            // Для обычных полей
            if (element.dataset.type === 'number') {
                current[lastKey] = parseInt(element.value, 10);
            } else if (element.dataset.type === 'float') {
                current[lastKey] = parseFloat(element.value);
            } else {
                current[lastKey] = element.value;
            }
        }
    });
    
    return config;
}

// Функция для отображения конфигурации
function renderConfig(config) {
    const container = document.getElementById('configContainer');
    container.innerHTML = ''; // Очищаем контейнер
    
    // Создаем секции для каждой категории
    const sections = {
        'settings': { key: 'SETTINGS', title: 'Settings', icon: 'cog' },
        'flow': { key: 'FLOW', title: 'Flow', icon: 'exchange-alt' },
        'faucet': { key: 'FAUCET', title: 'Faucet and Captcha', icon: 'robot' },
        'rpcs': { key: 'RPCS', title: 'RPCs', icon: 'network-wired' },
        'others': { key: 'OTHERS', title: 'Others', icon: 'ellipsis-h' },
        'swaps': { key: 'SWAPS', title: 'Swaps', icon: 'sync-alt' },
        'stakings': { key: 'STAKINGS', title: 'Stakings', icon: 'coins' },
        'mints': { key: 'MINTS', title: 'Mints', icon: 'hammer' },
        'crustyswap': { key: 'CRUSTY_SWAP', title: 'Crusty Swap', icon: 'network-wired' },
        'exchanges': { key: 'EXCHANGES', title: 'Exchanges', icon: 'exchange-alt' }
    };
    
    // Создаем все секции
    Object.entries(sections).forEach(([sectionId, { key, title, icon }], index) => {
        const section = document.createElement('div');
        section.id = `${sectionId}-section`;
        section.className = `config-section ${index === 0 ? 'active' : ''}`;
        
        const sectionTitle = document.createElement('h2');
        sectionTitle.className = 'section-title';
        sectionTitle.innerHTML = `<i class="fas fa-${icon}"></i> ${title}`;
        section.appendChild(sectionTitle);
        
        const cardsContainer = document.createElement('div');
        cardsContainer.className = 'config-cards';
        section.appendChild(cardsContainer);
        
        // Заполняем секцию данными
        if (config[key]) {
            if (key === 'SETTINGS') {
                // Карточка для основных настроек
                createCard(cardsContainer, 'Basic Settings', 'sliders-h', [
                    { key: 'THREADS', value: config[key]['THREADS'] },
                    { key: 'ATTEMPTS', value: config[key]['ATTEMPTS'] },
                    { key: 'SHUFFLE_WALLETS', value: config[key]['SHUFFLE_WALLETS'] },
                    { key: 'WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS', value: config[key]['WAIT_FOR_TRANSACTION_CONFIRMATION_IN_SECONDS'] }
                ], key);
                
                // Карточка для диапазонов аккаунтов
                createCard(cardsContainer, 'Account Settings', 'users', [
                    { key: 'ACCOUNTS_RANGE', value: config[key]['ACCOUNTS_RANGE'] },
                    { key: 'EXACT_ACCOUNTS_TO_USE', value: config[key]['EXACT_ACCOUNTS_TO_USE'], isSpaceList: true }
                ], key);
                
                // Карточка для пауз
                createCard(cardsContainer, 'Timing Settings', 'clock', [
                    { key: 'PAUSE_BETWEEN_ATTEMPTS', value: config[key]['PAUSE_BETWEEN_ATTEMPTS'] },
                    { key: 'PAUSE_BETWEEN_SWAPS', value: config[key]['PAUSE_BETWEEN_SWAPS'] },
                    { key: 'RANDOM_PAUSE_BETWEEN_ACCOUNTS', value: config[key]['RANDOM_PAUSE_BETWEEN_ACCOUNTS'] },
                    { key: 'RANDOM_PAUSE_BETWEEN_ACTIONS', value: config[key]['RANDOM_PAUSE_BETWEEN_ACTIONS'] },
                    { key: 'RANDOM_INITIALIZATION_PAUSE', value: config[key]['RANDOM_INITIALIZATION_PAUSE'] }
                ], key);
                
                // Карточка для Telegram
                createCard(cardsContainer, 'Telegram Settings', 'paper-plane', [
                    { key: 'SEND_TELEGRAM_LOGS', value: config[key]['SEND_TELEGRAM_LOGS'] },
                    { key: 'TELEGRAM_BOT_TOKEN', value: config[key]['TELEGRAM_BOT_TOKEN'] },
                    { key: 'TELEGRAM_USERS_IDS', value: config[key]['TELEGRAM_USERS_IDS'], isSpaceList: true }
                ], key);
            } else if (key === 'FLOW') {
                createCard(cardsContainer, 'Flow Settings', 'exchange-alt', [
                    { key: 'SKIP_FAILED_TASKS', value: config[key]['SKIP_FAILED_TASKS'] }
                ], key);
            } else if (key === 'FAUCET') {
                // Карточка для настроек Faucet
                createCard(cardsContainer, 'Captcha Solvers', 'puzzle-piece', [
                    { key: 'SOLVIUM_API_KEY', value: config[key]['SOLVIUM_API_KEY'] },
                    { key: 'USE_CAPSOLVER', value: config[key]['USE_CAPSOLVER'] },
                    { key: 'CAPSOLVER_API_KEY', value: config[key]['CAPSOLVER_API_KEY'] }
                ], key);
            } else if (key === 'RPCS') {
                // Специальная обработка для RPCs
                createCard(cardsContainer, 'RPC Settings', 'network-wired', 
                    Object.entries(config[key]).map(([k, v]) => ({ 
                        key: k, 
                        value: v, 
                        isList: true,
                        isArray: true  // Добавляем флаг для массивов
                    })), 
                    key
                );
            } else if (key === 'OTHERS') {
                // Остальные категории
                createCard(cardsContainer, `Other Settings`, icon, [
                    { key: 'SKIP_SSL_VERIFICATION', value: config[key]['SKIP_SSL_VERIFICATION'] },
                    { key: 'USE_PROXY_FOR_RPC', value: config[key]['USE_PROXY_FOR_RPC'] }
                ], key);
            } else if (key === 'SWAPS') {
                // BEBOP
                if (config[key]['BEBOP']) {
                    createCard(cardsContainer, 'Bebop Swap Settings', 'exchange', 
                        Object.entries(config[key]['BEBOP']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isRange: Array.isArray(v) && v.length === 2 && typeof v[0] === 'number',
                            isBoolean: typeof v === 'boolean'
                        })), 
                        `${key}.BEBOP`
                    );
                }
                
                // GTE
                if (config[key]['GTE']) {
                    createCard(cardsContainer, 'GTE Swap Settings', 'sync', 
                        Object.entries(config[key]['GTE']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isRange: Array.isArray(v) && v.length === 2 && typeof v[0] === 'number',
                            isBoolean: typeof v === 'boolean'
                        })), 
                        `${key}.GTE`
                    );
                }
            } else if (key === 'STAKINGS') {
                // TEKO_FINANCE
                if (config[key]['TEKO_FINANCE']) {
                    createCard(cardsContainer, 'Teko Finance Settings', 'chart-line', 
                        Object.entries(config[key]['TEKO_FINANCE']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isRange: Array.isArray(v) && v.length === 2 && typeof v[0] === 'number',
                            isNumber: typeof v === 'number' && !Array.isArray(v),
                            isBoolean: typeof v === 'boolean'
                        })), 
                        `${key}.TEKO_FINANCE`
                    );
                }
            } else if (key === 'MINTS') {
                // XL_MEME
                if (config[key]['XL_MEME']) {
                    createCard(cardsContainer, 'XL Meme Settings', 'fire', 
                        Object.entries(config[key]['XL_MEME']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isRange: Array.isArray(v) && v.length === 2,
                            isList: Array.isArray(v) && k === 'CONTRACTS_TO_BUY'
                        })), 
                        `${key}.XL_MEME`
                    );
                }

                // RARIBLE
                if (config[key]['RARIBLE']) {
                    createCard(cardsContainer, 'Rarible Settings', 'palette', 
                        Object.entries(config[key]['RARIBLE']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isList: Array.isArray(v) && k === 'CONTRACTS_TO_BUY'
                        })), 
                        `${key}.RARIBLE`
                    );
                }

                // OMNIHUB
                if (config[key]['OMNIHUB']) {
                    createCard(cardsContainer, 'OmniHub Settings', 'cube', 
                        Object.entries(config[key]['OMNIHUB']).map(([k, v]) => ({ 
                            key: k, 
                            value: v, 
                            isNumber: typeof v === 'number' && !Array.isArray(v)
                        })), 
                        `${key}.OMNIHUB`
                    );
                }
            } else if (key === 'CRUSTY_SWAP') {
                // CRUSTY_SWAP with more horizontal layout
                const cardDiv = document.createElement('div');
                cardDiv.className = 'config-card';
                
                const titleDiv = document.createElement('div');
                titleDiv.className = 'card-title';
                
                const icon = document.createElement('i');
                icon.className = 'fas fa-network-wired';
                titleDiv.appendChild(icon);
                
                const titleText = document.createElement('span');
                titleText.textContent = 'Crusty Swap Settings';
                titleDiv.appendChild(titleText);
                
                cardDiv.appendChild(titleDiv);
                
                // Networks to refuel from
                const networksFieldDiv = document.createElement('div');
                networksFieldDiv.className = 'config-field';
                
                const networksLabel = document.createElement('label');
                networksLabel.className = 'field-label';
                networksLabel.textContent = 'Networks to refuel from';
                networksFieldDiv.appendChild(networksLabel);
                
                const networksContainer = document.createElement('div');
                networksContainer.className = 'tags-input';
                networksContainer.dataset.configPath = `${key}.NETWORKS_TO_REFUEL_FROM`;
                
                // Predefined network options
                const availableNetworks = ['Arbitrum', 'Optimism', 'Base'];
                
                // Add existing networks as tags
                if (config[key].NETWORKS_TO_REFUEL_FROM && Array.isArray(config[key].NETWORKS_TO_REFUEL_FROM)) {
                    config[key].NETWORKS_TO_REFUEL_FROM.forEach(network => {
                        if (availableNetworks.includes(network)) {
                            const tag = document.createElement('div');
                            tag.className = 'tag';
                            
                            const tagText = document.createElement('span');
                            tagText.className = 'tag-text';
                            tagText.textContent = network;
                            
                            const removeBtn = document.createElement('button');
                            removeBtn.className = 'tag-remove';
                            removeBtn.innerHTML = '&times;';
                            removeBtn.addEventListener('click', function() {
                                tag.remove();
                            });
                            
                            tag.appendChild(tagText);
                            tag.appendChild(removeBtn);
                            networksContainer.appendChild(tag);
                        }
                    });
                }
                
                // Add dropdown for new networks
                const networksSelect = document.createElement('select');
                networksSelect.className = 'networks-select';
                networksSelect.style.background = 'transparent';
                networksSelect.style.border = 'none';
                networksSelect.style.color = 'var(--text-primary)';
                networksSelect.style.padding = '5px';
                
                const defaultOption = document.createElement('option');
                defaultOption.value = '';
                defaultOption.textContent = 'Add network...';
                defaultOption.selected = true;
                defaultOption.disabled = true;
                networksSelect.appendChild(defaultOption);
                
                availableNetworks.forEach(network => {
                    const option = document.createElement('option');
                    option.value = network;
                    option.textContent = network;
                    option.style.color = '#000';
                    option.style.background = '#fff';
                    networksSelect.appendChild(option);
                });
                
                networksSelect.addEventListener('change', function() {
                    if (this.value) {
                        // Check if network already exists
                        const tags = networksContainer.querySelectorAll('.tag-text');
                        let exists = false;
                        tags.forEach(tag => {
                            if (tag.textContent === this.value) {
                                exists = true;
                            }
                        });
                        
                        if (!exists) {
                            const tag = document.createElement('div');
                            tag.className = 'tag';
                            
                            const tagText = document.createElement('span');
                            tagText.className = 'tag-text';
                            tagText.textContent = this.value;
                            
                            const removeBtn = document.createElement('button');
                            removeBtn.className = 'tag-remove';
                            removeBtn.innerHTML = '&times;';
                            removeBtn.addEventListener('click', function() {
                                tag.remove();
                            });
                            
                            tag.appendChild(tagText);
                            tag.appendChild(removeBtn);
                            networksContainer.insertBefore(tag, this);
                        }
                        
                        // Reset select
                        this.value = '';
                    }
                });
                
                networksContainer.appendChild(networksSelect);
                networksFieldDiv.appendChild(networksContainer);
                cardDiv.appendChild(networksFieldDiv);
                
                // Amount to refuel - side by side min and max
                const amountFieldsDiv = document.createElement('div');
                amountFieldsDiv.className = 'config-field horizontal-fields';
                amountFieldsDiv.style.display = 'flex';
                amountFieldsDiv.style.gap = '15px';
                
                // Min amount field
                const minAmountDiv = document.createElement('div');
                minAmountDiv.style.flex = '1';
                
                const minAmountLabel = document.createElement('label');
                minAmountLabel.className = 'field-label';
                minAmountLabel.textContent = 'Amount (min)';
                minAmountDiv.appendChild(minAmountLabel);
                
                const minAmountInput = document.createElement('input');
                minAmountInput.type = 'number';
                minAmountInput.step = '0.0001';
                minAmountInput.className = 'field-input range-min';
                minAmountInput.value = config[key].AMOUNT_TO_REFUEL[0] || 0.0001;
                minAmountInput.dataset.configPath = `${key}.AMOUNT_TO_REFUEL_MIN`;
                minAmountInput.dataset.type = 'float';
                
                minAmountDiv.appendChild(minAmountInput);
                amountFieldsDiv.appendChild(minAmountDiv);
                
                // Max amount field
                const maxAmountDiv = document.createElement('div');
                maxAmountDiv.style.flex = '1';
                
                const maxAmountLabel = document.createElement('label');
                maxAmountLabel.className = 'field-label';
                maxAmountLabel.textContent = 'Amount (max)';
                maxAmountDiv.appendChild(maxAmountLabel);
                
                const maxAmountInput = document.createElement('input');
                maxAmountInput.type = 'number';
                maxAmountInput.step = '0.0001';
                maxAmountInput.className = 'field-input range-max';
                maxAmountInput.value = config[key].AMOUNT_TO_REFUEL[1] || 0.00015;
                maxAmountInput.dataset.configPath = `${key}.AMOUNT_TO_REFUEL_MAX`;
                maxAmountInput.dataset.type = 'float';
                
                maxAmountDiv.appendChild(maxAmountInput);
                amountFieldsDiv.appendChild(maxAmountDiv);
                
                cardDiv.appendChild(amountFieldsDiv);
                
                // 2-column layout for remaining options
                const optionsContainer = document.createElement('div');
                optionsContainer.style.display = 'flex';
                optionsContainer.style.flexWrap = 'wrap';
                optionsContainer.style.gap = '15px';
                
                // Minimum balance to refuel
                const minBalanceDiv = document.createElement('div');
                minBalanceDiv.className = 'config-field';
                minBalanceDiv.style.flex = '1';
                minBalanceDiv.style.minWidth = '200px';
                
                const minBalanceLabel = document.createElement('label');
                minBalanceLabel.className = 'field-label';
                minBalanceLabel.textContent = 'Minimum balance to refuel';
                minBalanceDiv.appendChild(minBalanceLabel);
                
                const minBalanceInput = document.createElement('input');
                minBalanceInput.type = 'number';
                minBalanceInput.step = '0.0001';
                minBalanceInput.className = 'field-input';
                minBalanceInput.value = config[key].MINIMUM_BALANCE_TO_REFUEL || 0;
                minBalanceInput.dataset.configPath = `${key}.MINIMUM_BALANCE_TO_REFUEL`;
                minBalanceInput.dataset.type = 'float';
                
                minBalanceDiv.appendChild(minBalanceInput);
                optionsContainer.appendChild(minBalanceDiv);
                
                // Bridge all max amount
                const bridgeMaxAmountDiv = document.createElement('div');
                bridgeMaxAmountDiv.className = 'config-field';
                bridgeMaxAmountDiv.style.flex = '1';
                bridgeMaxAmountDiv.style.minWidth = '200px';
                
                const bridgeMaxAmountLabel = document.createElement('label');
                bridgeMaxAmountLabel.className = 'field-label';
                bridgeMaxAmountLabel.textContent = 'Bridge all max amount';
                bridgeMaxAmountDiv.appendChild(bridgeMaxAmountLabel);
                
                const bridgeMaxAmountInput = document.createElement('input');
                bridgeMaxAmountInput.type = 'number';
                bridgeMaxAmountInput.step = '0.0001';
                bridgeMaxAmountInput.className = 'field-input';
                bridgeMaxAmountInput.value = config[key].BRIDGE_ALL_MAX_AMOUNT || 0.01;
                bridgeMaxAmountInput.dataset.configPath = `${key}.BRIDGE_ALL_MAX_AMOUNT`;
                bridgeMaxAmountInput.dataset.type = 'float';
                
                bridgeMaxAmountDiv.appendChild(bridgeMaxAmountInput);
                optionsContainer.appendChild(bridgeMaxAmountDiv);
                
                // Max wait time
                const maxWaitTimeDiv = document.createElement('div');
                maxWaitTimeDiv.className = 'config-field';
                maxWaitTimeDiv.style.flex = '1';
                maxWaitTimeDiv.style.minWidth = '200px';
                
                const maxWaitTimeLabel = document.createElement('label');
                maxWaitTimeLabel.className = 'field-label';
                maxWaitTimeLabel.textContent = 'Max wait time';
                maxWaitTimeDiv.appendChild(maxWaitTimeLabel);
                
                const maxWaitTimeInput = document.createElement('input');
                maxWaitTimeInput.type = 'number';
                maxWaitTimeInput.className = 'field-input';
                maxWaitTimeInput.value = config[key].MAX_WAIT_TIME || 99999;
                maxWaitTimeInput.dataset.configPath = `${key}.MAX_WAIT_TIME`;
                maxWaitTimeInput.dataset.type = 'number';
                
                maxWaitTimeDiv.appendChild(maxWaitTimeInput);
                optionsContainer.appendChild(maxWaitTimeDiv);
                
                // Create checkboxes in 2-column layout
                const checkboxesContainer = document.createElement('div');
                checkboxesContainer.style.display = 'flex';
                checkboxesContainer.style.gap = '20px';
                checkboxesContainer.style.marginTop = '10px';
                
                // Wait for funds checkbox
                const waitFundsDiv = document.createElement('div');
                waitFundsDiv.className = 'checkbox-field';
                waitFundsDiv.style.flex = '1';
                
                const waitFundsInput = document.createElement('input');
                waitFundsInput.type = 'checkbox';
                waitFundsInput.className = 'checkbox-input';
                waitFundsInput.checked = config[key].WAIT_FOR_FUNDS_TO_ARRIVE || false;
                waitFundsInput.dataset.configPath = `${key}.WAIT_FOR_FUNDS_TO_ARRIVE`;
                waitFundsInput.id = `checkbox-wait-funds-crusty`;
                
                const waitFundsLabel = document.createElement('label');
                waitFundsLabel.className = 'checkbox-label';
                waitFundsLabel.textContent = 'Wait for funds to arrive';
                waitFundsLabel.htmlFor = waitFundsInput.id;
                
                waitFundsDiv.appendChild(waitFundsInput);
                waitFundsDiv.appendChild(waitFundsLabel);
                checkboxesContainer.appendChild(waitFundsDiv);
                
                // Bridge all checkbox
                const bridgeAllDiv = document.createElement('div');
                bridgeAllDiv.className = 'checkbox-field';
                bridgeAllDiv.style.flex = '1';
                
                const bridgeAllInput = document.createElement('input');
                bridgeAllInput.type = 'checkbox';
                bridgeAllInput.className = 'checkbox-input';
                bridgeAllInput.checked = config[key].BRIDGE_ALL || false;
                bridgeAllInput.dataset.configPath = `${key}.BRIDGE_ALL`;
                bridgeAllInput.id = `checkbox-bridge-all`;
                
                const bridgeAllLabel = document.createElement('label');
                bridgeAllLabel.className = 'checkbox-label';
                bridgeAllLabel.textContent = 'Bridge all';
                bridgeAllLabel.htmlFor = bridgeAllInput.id;
                
                bridgeAllDiv.appendChild(bridgeAllInput);
                bridgeAllDiv.appendChild(bridgeAllLabel);
                checkboxesContainer.appendChild(bridgeAllDiv);
                
                optionsContainer.appendChild(checkboxesContainer);
                cardDiv.appendChild(optionsContainer);
                
                cardsContainer.appendChild(cardDiv);
            } else if (key === 'EXCHANGES') {
                // Basic exchange settings (exclude withdrawals)
                const exchangeCardDiv = document.createElement('div');
                exchangeCardDiv.className = 'config-card';
                
                const exchangeTitleDiv = document.createElement('div');
                exchangeTitleDiv.className = 'card-title';
                
                const exchangeIcon = document.createElement('i');
                exchangeIcon.className = 'fas fa-exchange-alt';
                exchangeTitleDiv.appendChild(exchangeIcon);
                
                const exchangeTitleText = document.createElement('span');
                exchangeTitleText.textContent = 'Exchange Settings';
                exchangeTitleDiv.appendChild(exchangeTitleText);
                
                exchangeCardDiv.appendChild(exchangeTitleDiv);
                
                // Exchange name - dropdown instead of text input
                const nameFieldDiv = document.createElement('div');
                nameFieldDiv.className = 'config-field';
                
                const nameLabel = document.createElement('label');
                nameLabel.className = 'field-label';
                nameLabel.textContent = 'Name';
                nameFieldDiv.appendChild(nameLabel);
                
                const nameSelect = document.createElement('select');
                nameSelect.className = 'field-input';
                nameSelect.dataset.configPath = `${key}.name`;
                
                const options = ['OKX', 'BITGET'];
                options.forEach(opt => {
                    const option = document.createElement('option');
                    option.value = opt;
                    option.textContent = opt;
                    if (config[key].name === opt) {
                        option.selected = true;
                    }
                    nameSelect.appendChild(option);
                });
                
                nameFieldDiv.appendChild(nameSelect);
                exchangeCardDiv.appendChild(nameFieldDiv);
                
                // API Key field
                const apiKeyFieldDiv = document.createElement('div');
                apiKeyFieldDiv.className = 'config-field';
                
                const apiKeyLabel = document.createElement('label');
                apiKeyLabel.className = 'field-label';
                apiKeyLabel.textContent = 'API Key';
                apiKeyFieldDiv.appendChild(apiKeyLabel);
                
                const apiKeyInput = document.createElement('input');
                apiKeyInput.type = 'text';
                apiKeyInput.className = 'field-input';
                apiKeyInput.value = config[key].apiKey || '';
                apiKeyInput.dataset.configPath = `${key}.apiKey`;
                
                apiKeyFieldDiv.appendChild(apiKeyInput);
                exchangeCardDiv.appendChild(apiKeyFieldDiv);
                
                // Secret Key field
                const secretKeyFieldDiv = document.createElement('div');
                secretKeyFieldDiv.className = 'config-field';
                
                const secretKeyLabel = document.createElement('label');
                secretKeyLabel.className = 'field-label';
                secretKeyLabel.textContent = 'Secret Key';
                secretKeyFieldDiv.appendChild(secretKeyLabel);
                
                const secretKeyInput = document.createElement('input');
                secretKeyInput.type = 'text';
                secretKeyInput.className = 'field-input';
                secretKeyInput.value = config[key].secretKey || '';
                secretKeyInput.dataset.configPath = `${key}.secretKey`;
                
                secretKeyFieldDiv.appendChild(secretKeyInput);
                exchangeCardDiv.appendChild(secretKeyFieldDiv);
                
                // Passphrase field
                const passphraseFieldDiv = document.createElement('div');
                passphraseFieldDiv.className = 'config-field';
                
                const passphraseLabel = document.createElement('label');
                passphraseLabel.className = 'field-label';
                passphraseLabel.textContent = 'Passphrase';
                passphraseFieldDiv.appendChild(passphraseLabel);
                
                const passphraseInput = document.createElement('input');
                passphraseInput.type = 'text';
                passphraseInput.className = 'field-input';
                passphraseInput.value = config[key].passphrase || '';
                passphraseInput.dataset.configPath = `${key}.passphrase`;
                
                passphraseFieldDiv.appendChild(passphraseInput);
                exchangeCardDiv.appendChild(passphraseFieldDiv);
                
                cardsContainer.appendChild(exchangeCardDiv);
                
                // Create withdrawal settings card with more horizontal layout
                if (config[key].withdrawals && config[key].withdrawals.length > 0) {
                    const withdrawalConfig = config[key].withdrawals[0];
                    
                    const withdrawalCardDiv = document.createElement('div');
                    withdrawalCardDiv.className = 'config-card';
                    
                    const withdrawalTitleDiv = document.createElement('div');
                    withdrawalTitleDiv.className = 'card-title';
                    
                    const withdrawalIcon = document.createElement('i');
                    withdrawalIcon.className = 'fas fa-money-bill-transfer';
                    withdrawalTitleDiv.appendChild(withdrawalIcon);
                    
                    const withdrawalTitleText = document.createElement('span');
                    withdrawalTitleText.textContent = 'Withdrawal Settings';
                    withdrawalTitleDiv.appendChild(withdrawalTitleText);
                    
                    withdrawalCardDiv.appendChild(withdrawalTitleDiv);
                    
                    // Currency field - hardcoded to ETH
                    const currencyFieldDiv = document.createElement('div');
                    currencyFieldDiv.className = 'config-field';
                    
                    const currencyLabel = document.createElement('label');
                    currencyLabel.className = 'field-label';
                    currencyLabel.textContent = 'Currency';
                    currencyFieldDiv.appendChild(currencyLabel);
                    
                    const currencyInput = document.createElement('input');
                    currencyInput.type = 'text';
                    currencyInput.className = 'field-input';
                    currencyInput.value = 'ETH';
                    currencyInput.readOnly = true;
                    currencyInput.disabled = true;
                    currencyInput.dataset.configPath = `${key}.withdrawals[0].currency`;
                    
                    currencyFieldDiv.appendChild(currencyInput);
                    withdrawalCardDiv.appendChild(currencyFieldDiv);
                    
                    // Networks field - multi-select with predefined options
                    const networksFieldDiv = document.createElement('div');
                    networksFieldDiv.className = 'config-field';
                    
                    const networksLabel = document.createElement('label');
                    networksLabel.className = 'field-label';
                    networksLabel.textContent = 'Networks';
                    networksFieldDiv.appendChild(networksLabel);
                    
                    const networksContainer = document.createElement('div');
                    networksContainer.className = 'tags-input';
                    networksContainer.dataset.configPath = `${key}.withdrawals[0].networks`;
                    
                    // Predefined network options
                    const availableNetworks = ['Arbitrum', 'Optimism', 'Base'];
                    
                    // Add existing networks as tags
                    if (withdrawalConfig.networks && Array.isArray(withdrawalConfig.networks)) {
                        withdrawalConfig.networks.forEach(network => {
                            if (availableNetworks.includes(network)) {
                                const tag = document.createElement('div');
                                tag.className = 'tag';
                                
                                const tagText = document.createElement('span');
                                tagText.className = 'tag-text';
                                tagText.textContent = network;
                                
                                const removeBtn = document.createElement('button');
                                removeBtn.className = 'tag-remove';
                                removeBtn.innerHTML = '&times;';
                                removeBtn.addEventListener('click', function() {
                                    tag.remove();
                                });
                                
                                tag.appendChild(tagText);
                                tag.appendChild(removeBtn);
                                networksContainer.appendChild(tag);
                            }
                        });
                    }
                    
                    // Add dropdown for new networks
                    const networksSelect = document.createElement('select');
                    networksSelect.className = 'networks-select';
                    networksSelect.style.background = 'transparent';
                    networksSelect.style.border = 'none';
                    networksSelect.style.color = 'var(--text-primary)';
                    networksSelect.style.padding = '5px';
                    
                    const defaultOption = document.createElement('option');
                    defaultOption.value = '';
                    defaultOption.textContent = 'Add network...';
                    defaultOption.selected = true;
                    defaultOption.disabled = true;
                    networksSelect.appendChild(defaultOption);
                    
                    availableNetworks.forEach(network => {
                        const option = document.createElement('option');
                        option.value = network;
                        option.textContent = network;
                        option.style.color = '#000';
                        option.style.background = '#fff';
                        networksSelect.appendChild(option);
                    });
                    
                    networksSelect.addEventListener('change', function() {
                        if (this.value) {
                            // Check if network already exists
                            const tags = networksContainer.querySelectorAll('.tag-text');
                            let exists = false;
                            tags.forEach(tag => {
                                if (tag.textContent === this.value) {
                                    exists = true;
                                }
                            });
                            
                            if (!exists) {
                                const tag = document.createElement('div');
                                tag.className = 'tag';
                                
                                const tagText = document.createElement('span');
                                tagText.className = 'tag-text';
                                tagText.textContent = this.value;
                                
                                const removeBtn = document.createElement('button');
                                removeBtn.className = 'tag-remove';
                                removeBtn.innerHTML = '&times;';
                                removeBtn.addEventListener('click', function() {
                                    tag.remove();
                                });
                                
                                tag.appendChild(tagText);
                                tag.appendChild(removeBtn);
                                networksContainer.insertBefore(tag, this);
                            }
                            
                            // Reset select
                            this.value = '';
                        }
                    });
                    
                    networksContainer.appendChild(networksSelect);
                    networksFieldDiv.appendChild(networksContainer);
                    withdrawalCardDiv.appendChild(networksFieldDiv);
                    
                    // Min and Max amount fields side by side
                    const amountFieldsDiv = document.createElement('div');
                    amountFieldsDiv.className = 'config-field horizontal-fields';
                    amountFieldsDiv.style.display = 'flex';
                    amountFieldsDiv.style.gap = '15px';
                    
                    // Min amount field
                    const minAmountDiv = document.createElement('div');
                    minAmountDiv.style.flex = '1';
                    
                    const minAmountLabel = document.createElement('label');
                    minAmountLabel.className = 'field-label';
                    minAmountLabel.textContent = 'Min amount';
                    minAmountDiv.appendChild(minAmountLabel);
                    
                    const minAmountInput = document.createElement('input');
                    minAmountInput.type = 'number';
                    minAmountInput.step = '0.0001';
                    minAmountInput.className = 'field-input';
                    minAmountInput.value = withdrawalConfig.min_amount || 0.0003;
                    minAmountInput.dataset.configPath = `${key}.withdrawals[0].min_amount`;
                    minAmountInput.dataset.type = 'float';
                    
                    minAmountDiv.appendChild(minAmountInput);
                    amountFieldsDiv.appendChild(minAmountDiv);
                    
                    // Max amount field
                    const maxAmountDiv = document.createElement('div');
                    maxAmountDiv.style.flex = '1';
                    
                    const maxAmountLabel = document.createElement('label');
                    maxAmountLabel.className = 'field-label';
                    maxAmountLabel.textContent = 'Max amount';
                    maxAmountDiv.appendChild(maxAmountLabel);
                    
                    const maxAmountInput = document.createElement('input');
                    maxAmountInput.type = 'number';
                    maxAmountInput.step = '0.0001';
                    maxAmountInput.className = 'field-input';
                    maxAmountInput.value = withdrawalConfig.max_amount || 0.0004;
                    maxAmountInput.dataset.configPath = `${key}.withdrawals[0].max_amount`;
                    maxAmountInput.dataset.type = 'float';
                    
                    maxAmountDiv.appendChild(maxAmountInput);
                    amountFieldsDiv.appendChild(maxAmountDiv);
                    
                    withdrawalCardDiv.appendChild(amountFieldsDiv);
                    
                    // Max balance field
                    const maxBalanceFieldDiv = document.createElement('div');
                    maxBalanceFieldDiv.className = 'config-field';
                    
                    const maxBalanceLabel = document.createElement('label');
                    maxBalanceLabel.className = 'field-label';
                    maxBalanceLabel.textContent = 'Max balance';
                    maxBalanceFieldDiv.appendChild(maxBalanceLabel);
                    
                    const maxBalanceInput = document.createElement('input');
                    maxBalanceInput.type = 'number';
                    maxBalanceInput.step = '0.0001';
                    maxBalanceInput.className = 'field-input';
                    maxBalanceInput.value = withdrawalConfig.max_balance || 0.005;
                    maxBalanceInput.dataset.configPath = `${key}.withdrawals[0].max_balance`;
                    maxBalanceInput.dataset.type = 'float';
                    
                    maxBalanceFieldDiv.appendChild(maxBalanceInput);
                    withdrawalCardDiv.appendChild(maxBalanceFieldDiv);
                    
                    // Horizontal layout for checkboxes and related fields
                    const optionsFieldsDiv = document.createElement('div');
                    optionsFieldsDiv.className = 'config-field';
                    optionsFieldsDiv.style.display = 'flex';
                    optionsFieldsDiv.style.flexWrap = 'wrap';
                    optionsFieldsDiv.style.gap = '20px';
                    
                    // Wait for funds checkbox
                    const waitFundsDiv = document.createElement('div');
                    waitFundsDiv.className = 'checkbox-field';
                    waitFundsDiv.style.flex = '1';
                    
                    const waitFundsInput = document.createElement('input');
                    waitFundsInput.type = 'checkbox';
                    waitFundsInput.className = 'checkbox-input';
                    waitFundsInput.checked = withdrawalConfig.wait_for_funds || false;
                    waitFundsInput.dataset.configPath = `${key}.withdrawals[0].wait_for_funds`;
                    waitFundsInput.id = `checkbox-wait-funds`;
                    
                    const waitFundsLabel = document.createElement('label');
                    waitFundsLabel.className = 'checkbox-label';
                    waitFundsLabel.textContent = 'Wait for funds';
                    waitFundsLabel.htmlFor = waitFundsInput.id;
                    
                    waitFundsDiv.appendChild(waitFundsInput);
                    waitFundsDiv.appendChild(waitFundsLabel);
                    optionsFieldsDiv.appendChild(waitFundsDiv);
                    
                    // Max wait time field
                    const maxWaitTimeDiv = document.createElement('div');
                    maxWaitTimeDiv.style.flex = '1';
                    maxWaitTimeDiv.style.minWidth = '200px';
                    
                    const maxWaitTimeLabel = document.createElement('label');
                    maxWaitTimeLabel.className = 'field-label';
                    maxWaitTimeLabel.textContent = 'Max wait time';
                    maxWaitTimeDiv.appendChild(maxWaitTimeLabel);
                    
                    const maxWaitTimeInput = document.createElement('input');
                    maxWaitTimeInput.type = 'number';
                    maxWaitTimeInput.className = 'field-input';
                    maxWaitTimeInput.value = withdrawalConfig.max_wait_time || 99999;
                    maxWaitTimeInput.dataset.configPath = `${key}.withdrawals[0].max_wait_time`;
                    maxWaitTimeInput.dataset.type = 'number';
                    
                    maxWaitTimeDiv.appendChild(maxWaitTimeInput);
                    optionsFieldsDiv.appendChild(maxWaitTimeDiv);
                    
                    // Retries field
                    const retriesDiv = document.createElement('div');
                    retriesDiv.style.flex = '1';
                    retriesDiv.style.minWidth = '200px';
                    
                    const retriesLabel = document.createElement('label');
                    retriesLabel.className = 'field-label';
                    retriesLabel.textContent = 'Retries';
                    retriesDiv.appendChild(retriesLabel);
                    
                    const retriesInput = document.createElement('input');
                    retriesInput.type = 'number';
                    retriesInput.className = 'field-input small-input';
                    retriesInput.value = withdrawalConfig.retries || 3;
                    retriesInput.dataset.configPath = `${key}.withdrawals[0].retries`;
                    retriesInput.dataset.type = 'number';
                    
                    retriesDiv.appendChild(retriesInput);
                    optionsFieldsDiv.appendChild(retriesDiv);
                    
                    withdrawalCardDiv.appendChild(optionsFieldsDiv);
                    
                    cardsContainer.appendChild(withdrawalCardDiv);
                }
            }
        }
        
        container.appendChild(section);
    });
}

// Функция для создания карточки
function createCard(container, title, iconClass, fields, category) {
    const cardDiv = document.createElement('div');
    cardDiv.className = 'config-card';
    
    const titleDiv = document.createElement('div');
    titleDiv.className = 'card-title';
    
    const icon = document.createElement('i');
    icon.className = `fas fa-${iconClass}`;
    titleDiv.appendChild(icon);
    
    const titleText = document.createElement('span');
    titleText.textContent = title;
    titleDiv.appendChild(titleText);
    
    cardDiv.appendChild(titleDiv);
    
    fields.forEach(({ key, value, isList, isSpaceList, isRange, isBoolean, isNumber }) => {
        if (isBoolean || typeof value === 'boolean') {
            createCheckboxField(cardDiv, key, value, `${category}.${key}`);
        } else if (isRange || (Array.isArray(value) && value.length === 2 && typeof value[0] === 'number' && typeof value[1] === 'number')) {
            createRangeField(cardDiv, key, value, `${category}.${key}`);
        } else if (isList || (Array.isArray(value) && !isRange)) {
            createTagsField(cardDiv, key, value, `${category}.${key}`, isSpaceList);
        } else if (isNumber || typeof value === 'number') {
            createTextField(cardDiv, key, value, `${category}.${key}`);
        } else {
            createTextField(cardDiv, key, value, `${category}.${key}`);
        }
    });
    
    container.appendChild(cardDiv);
}

// Создание текстового поля
function createTextField(container, key, value, path) {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'config-field';
    
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = formatFieldName(key);
    fieldDiv.appendChild(label);
    
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'field-input';
    input.value = value;
    input.dataset.configPath = path;
    
    if (typeof value === 'number') {
        input.dataset.type = 'number';
        input.type = 'number';
        input.className += ' small-input';
    }
    
    fieldDiv.appendChild(input);
    container.appendChild(fieldDiv);
}

// Создание поля диапазона
function createRangeField(container, key, value, path) {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'config-field';
    
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = formatFieldName(key);
    fieldDiv.appendChild(label);
    
    // Check if this is a float value field (used in EXCHANGES and CRUSTY_SWAP)
    const isFloatField = path.includes('min_amount') || 
                          path.includes('max_amount') || 
                          path.includes('max_balance') || 
                          path.includes('AMOUNT_TO_REFUEL') ||
                          path.includes('MINIMUM_BALANCE_TO_REFUEL') ||
                          path.includes('BRIDGE_ALL_MAX_AMOUNT');
    
    // For single values that need to be treated as ranges (withdrawal settings)
    if (!Array.isArray(value)) {
        const input = document.createElement('input');
        input.type = 'number';
        input.className = 'field-input small-input';
        input.value = value;
        input.dataset.configPath = path;
        
        if (isFloatField) {
            input.step = '0.0001';
            input.dataset.type = 'float';
        } else {
            input.dataset.type = 'number';
        }
        
        fieldDiv.appendChild(input);
        container.appendChild(fieldDiv);
        return;
    }
    
    const rangeDiv = document.createElement('div');
    rangeDiv.className = 'range-input';
    
    const minInput = document.createElement('input');
    minInput.type = 'number';
    minInput.className = 'field-input range-min small-input';
    minInput.value = value[0];
    minInput.dataset.configPath = `${path}_MIN`;
    
    if (isFloatField) {
        minInput.step = '0.0001';
        minInput.dataset.type = 'float';
    } else {
        minInput.dataset.type = 'number';
    }
    
    const separator = document.createElement('span');
    separator.className = 'range-separator';
    separator.textContent = '-';
    
    const maxInput = document.createElement('input');
    maxInput.type = 'number';
    maxInput.className = 'field-input range-max small-input';
    maxInput.value = value[1];
    maxInput.dataset.configPath = `${path}_MAX`;
    
    if (isFloatField) {
        maxInput.step = '0.0001';
        maxInput.dataset.type = 'float';
    } else {
        maxInput.dataset.type = 'number';
    }
    
    rangeDiv.appendChild(minInput);
    rangeDiv.appendChild(separator);
    rangeDiv.appendChild(maxInput);
    
    fieldDiv.appendChild(rangeDiv);
    container.appendChild(fieldDiv);
}

// Создание чекбокса
function createCheckboxField(container, key, value, path) {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'checkbox-field';
    
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.className = 'checkbox-input';
    input.checked = value;
    input.dataset.configPath = path;
    input.id = `checkbox-${path.replace(/\\./g, '-')}`;
    
    const label = document.createElement('label');
    label.className = 'checkbox-label';
    label.textContent = formatFieldName(key);
    label.htmlFor = input.id;
    
    fieldDiv.appendChild(input);
    fieldDiv.appendChild(label);
    container.appendChild(fieldDiv);
}

// Создание списка
function createListField(container, key, value, path) {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'config-field';
    
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = formatFieldName(key);
    fieldDiv.appendChild(label);
    
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'field-input list-input';
    input.value = value.join(', ');
    input.dataset.configPath = path;
    
    // Определяем, является ли это списком чисел
    if (value.length > 0 && typeof value[0] === 'number') {
        input.dataset.type = 'number-list';
    }
    
    fieldDiv.appendChild(input);
    container.appendChild(fieldDiv);
}

// Создание поля с тегами (для списков)
function createTagsField(container, key, value, path, useSpaces) {
    const fieldDiv = document.createElement('div');
    fieldDiv.className = 'config-field';
    
    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = formatFieldName(key);
    fieldDiv.appendChild(label);
    
    const tagsContainer = document.createElement('div');
    tagsContainer.className = 'tags-input';
    tagsContainer.dataset.configPath = path;
    tagsContainer.dataset.useSpaces = useSpaces ? 'true' : 'false';
    
    // Убедимся, что value является массивом
    const values = Array.isArray(value) ? value : [value];
    
    // Добавляем существующие теги
    values.forEach(item => {
        if (item !== null && item !== undefined) {
            const tag = createTag(item.toString());
            tagsContainer.appendChild(tag);
        }
    });
    
    // Добавляем поле ввода для новых тегов
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Add item...';
    
    // Обработчик для добавления нового тега
    input.addEventListener('keydown', function(e) {
        if ((e.key === 'Enter') || (e.key === ' ' && useSpaces)) {
            e.preventDefault();
            const value = this.value.trim();
            if (value) {
                const tag = createTag(value);
                tagsContainer.insertBefore(tag, this);
                this.value = '';
            }
        }
    });
    
    tagsContainer.appendChild(input);
    
    // Функция для создания тега
    function createTag(text) {
        const tag = document.createElement('div');
        tag.className = 'tag';
        
        const tagText = document.createElement('span');
        tagText.className = 'tag-text';
        tagText.textContent = text;
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'tag-remove';
        removeBtn.innerHTML = '&times;';
        removeBtn.addEventListener('click', function() {
            tag.remove();
        });
        
        tag.appendChild(tagText);
        tag.appendChild(removeBtn);
        
        return tag;
    }
    
    fieldDiv.appendChild(tagsContainer);
    container.appendChild(fieldDiv);
}

// Функция для отображения уведомления
function showNotification(message, type) {
    const notification = document.getElementById('notification');
    notification.className = `notification ${type} show`;
    
    document.getElementById('notification-message').textContent = message;
    
    setTimeout(() => {
        notification.className = 'notification';
    }, 3000);
}
"""

        # Записываем файлы в соответствующие директории
        template_path = os.path.join(template_dir, "config.html")
        css_path = os.path.join(css_dir, "style.css")
        js_path = os.path.join(js_dir, "config.js")

        with open(template_path, "w", encoding="utf-8") as file:
            file.write(html_template)

        with open(css_path, "w", encoding="utf-8") as file:
            file.write(css_content)

        with open(js_path, "w", encoding="utf-8") as file:
            file.write(js_content)

        # Проверяем, что файлы созданы
        logger.info(f"Template file created: {os.path.exists(template_path)}")
        logger.info(f"CSS file created: {os.path.exists(css_path)}")
        logger.info(f"JS file created: {os.path.exists(js_path)}")

    except Exception as e:
        logger.error(f"Error creating directories: {str(e)}")
        logger.error(traceback.format_exc())
        raise


def check_paths():
    """Проверяет пути к файлам и директориям"""
    try:
        base_dir = os.path.dirname(__file__)
        logger.info(f"Base directory: {base_dir}")

        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
        logger.info(f"Config path: {config_path}")
        logger.info(f"Config exists: {os.path.exists(config_path)}")

        template_dir = os.path.join(base_dir, "config_interface", "templates")
        logger.info(f"Template directory: {template_dir}")
        logger.info(f"Template directory exists: {os.path.exists(template_dir)}")

        return True
    except Exception as e:
        logger.error(f"Path check failed: {str(e)}")
        return False


def run():
    """Запускает веб-интерфейс для редактирования конфигурации"""
    try:
        # Создаем необходимые директории и файлы
        create_required_directories()

        # Запускаем браузер в отдельном потоке
        threading.Thread(target=open_browser).start()

        # Выводим информацию о запуске
        logger.info("Starting web configuration interface...")
        logger.info(f"Configuration interface available at: http://127.0.0.1:3456")
        logger.info(f"To exit and return to main menu: Press CTRL+C")

        # Отключаем логи Werkzeug
        log = logging.getLogger("werkzeug")
        log.disabled = True
        app.logger.disabled = True

        # Запускаем Flask
        app.run(debug=False, port=3456)
    except KeyboardInterrupt:
        logger.info("Web configuration interface stopped")
    except Exception as e:
        logger.error(f"Failed to start web interface: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"ERROR: {str(e)}")
