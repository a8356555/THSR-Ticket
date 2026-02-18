import sys
import argparse
import logging
import yaml
import os

sys.path.append("./")

from thsr_ticket.model.db import ParamDB
from thsr_ticket.controller.planner import Planner
from thsr_ticket.controller.buyer import Buyer
from thsr_ticket.controller.manager import Manager

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from thsr_ticket.configs.config_schema import AppConfig
from pydantic import ValidationError

def load_config() -> dict:
    try:
        with open('config.yaml', 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f) or {}

        # Validate Config
        try:
            validated_config = AppConfig(**raw_config)
            # Return dict for compatibility with existing code that expects dict
            # or refactor app to use Pydantic model.
            # For minimal invasion, return validated_config.dict() (v1) or model_dump() (v2)
            # Check pydantic version in requirements?
            # safe option: getattr(validated_config, 'model_dump', validated_config.dict)()
            return validated_config.dict()
        except ValidationError as e:
            logger.error(f"Config Validation Failed: {e}")
            sys.exit(1)

    except FileNotFoundError:
        logger.error("config.yaml not found!")
        return {}

def main():
    parser = argparse.ArgumentParser(description="THSR Ticket Rolling Reservation Bot")
    parser.add_argument(
        "--mode",
        choices=["plan", "buy", "manage", "auto"],
        default="auto",
        help="Operation mode: plan (generate queue), buy (execute queue), manage (check history), auto (all)"
    )
    args = parser.parse_args()

    db = ParamDB()
    config = load_config()

    if args.mode in ["plan", "auto"]:
        logger.info(">>> Starting Planner Phase")
        Planner(config, db).run()

    if args.mode in ["buy", "auto"]:
        logger.info(">>> Starting Buyer Phase")
        Buyer(db, config).run()

    if args.mode in ["manage", "auto"]:
        logger.info(">>> Starting Manager Phase")
        Manager(db, config).run()

if __name__ == "__main__":
    main()
