"""Configuration and logging utilities."""

import os
import logging
from pathlib import Path

def setup_logging(log_path: Path) -> None:
    """Configure logging to write detailed logs to file and simplified output to console.
    
    Args:
        log_path: Path where the log file will be written
    """

    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Remove any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    
    ##      FORMATTERS      ##
    # logfile formatter
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # console formatter
    console_formatter = logging.Formatter('%(message)s')

    ##      HANDLERS      ##
    # File handler - captures everything
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    # Console handler - only shows essential info
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Create a filter for the console handler
    class ConsoleFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            # Add console-specific filtering here
            # Example: only show trade messages and errors
            return (
                record.levelno >= logging.ERROR or
                "Trade Request" in record.msg or
                "Starting" in record.msg or
                "Shutting down" in record.msg
            )
    
    console_handler.addFilter(ConsoleFilter())
    
    # Configure root logger
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def load_dotenv(path: Path) -> dict:
    """Load environment variables from a .env file.
    
    Returns:
        dict: Dictionary of loaded variables and their values.
    """
    loaded_vars = {}
    if not path.exists():
        return loaded_vars

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)
            loaded_vars[k] = v

    return loaded_vars

def validate_config(required_vars: list[str]) -> tuple[bool, list[str]]:
    """Validate that all required environment variables are set.
    
    Args:
        required_vars: List of required environment variable names.
    
    Returns:
        tuple: (is_valid, missing_vars)
    """
    missing = [var for var in required_vars if not os.getenv(var)]
    return len(missing) == 0, missing

def find_dotenv() -> Path:
    """Find the .env file in various possible locations."""
    # Check in order:
    # 1. Current working directory
    # 2. Script directory
    # 3. User's home directory
    # 4. %LOCALAPPDATA%/NavalisOracle

    possible_locations = [
        Path.cwd() / ".env",
        Path(__file__).parent.parent / ".env",
        Path.home() / ".env",
        Path(os.getenv("LOCALAPPDATA", Path.home())) / "NavalisOracle" / ".env"
    ]

    for path in possible_locations:
        if path.is_file():
            return path

    # If no .env found, return the default location (script dir)
    return possible_locations[1]

def get_app_paths() -> tuple[Path, Path, Path]:
    """Get application paths for config, logs, and data."""

    app_data = Path(os.getenv("LOCALAPPDATA", Path.home())) / "NavalisOracle"
    app_data.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).parent.parent
    env_file = find_dotenv()
    log_file = app_data / "pigeoneer.log"

    return script_dir, env_file, log_file
