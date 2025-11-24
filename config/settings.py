import os
from pathlib import Path
from typing import Any, Dict

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"


def load_config(path: str = None) -> Dict[str, Any]:
    """Load YAML config file into a dictionary with environment variable overrides."""
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found at {config_path}")
    with config_path.open("r") as fh:
        config = yaml.safe_load(fh) or {}
    apply_env_overrides(config)
    return config


def apply_env_overrides(config: Dict[str, Any]) -> None:
    """Override config entries with environment variables using upper snake case keys."""
    broker_cfg = config.get("broker", {})
    broker_cfg["api_key"] = os.getenv("KITE_API_KEY", broker_cfg.get("api_key"))
    broker_cfg["api_secret"] = os.getenv("KITE_API_SECRET", broker_cfg.get("api_secret"))
    broker_cfg["access_token"] = os.getenv("KITE_ACCESS_TOKEN", broker_cfg.get("access_token"))
    config["broker"] = broker_cfg
    notif_cfg = config.get("notifications", {})
    notif_cfg["slack_webhook"] = os.getenv("SLACK_WEBHOOK", notif_cfg.get("slack_webhook"))
    notif_cfg["telegram_bot_token"] = os.getenv("TELEGRAM_BOT_TOKEN", notif_cfg.get("telegram_bot_token"))
    notif_cfg["telegram_chat_id"] = os.getenv("TELEGRAM_CHAT_ID", notif_cfg.get("telegram_chat_id"))
    config["notifications"] = notif_cfg


def get_strategy_classes(config: Dict[str, Any]) -> Dict[str, str]:
    strategies = {}
    for entry in config.get("strategies", []):
        if entry.get("enabled", True):
            strategies[entry["name"]] = entry["class"]
    return strategies
