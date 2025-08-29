import time
import re
import os
import sys
import json
import logging
from pathlib import Path
from urllib import parse, request, error

def setup_logging(log_path: Path) -> None:
    """Configure logging to write to both file and console"""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create formatters and handlers
    file_formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter('%(message)s')
    
    # File handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

def _load_dotenv(path: Path) -> None:
    """Load environment variables from a .env file"""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            os.environ.setdefault(k, v)

# Maximum length for Telegram messages
MAX_LEN = 4096

def _tg_api(token: str, method: str, data: dict | None = None, timeout: int = 20) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        if data:
            enc = parse.urlencode({k: str(v) for k, v in data.items()}).encode("utf-8")
            req = request.Request(url, data=enc, method="POST")
        else:
            req = request.Request(url, method="GET")
        with request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {e.code}: {body}")
    except Exception as e:
        raise RuntimeError(f"API call failed: {e!r}")

def _send_telegram(text: str, chat_id: str, token: str, parse_mode: str | None = None,
                  disable_preview: bool | None = None, silent: bool | None = None) -> dict:
    data = {"chat_id": chat_id, "text": text}
    if parse_mode:
        pm = parse_mode.upper()
        if pm in {"HTML", "MARKDOWN", "MARKDOWNV2"}:
            data["parse_mode"] = pm
    if disable_preview is not None:
        data["disable_web_page_preview"] = "true" if disable_preview else "false"
    if silent:
        data["disable_notification"] = "true"

    return _tg_api(token, "sendMessage", data)

def send_message(text: str, chat_id: str, token: str, parse_mode: str | None = None,
                disable_preview: bool | None = True, silent: bool | None = None) -> None:
    """Send a message via Telegram, automatically handling message length limits."""
    if len(text) <= MAX_LEN:
        _send_telegram(text, chat_id, token, parse_mode, disable_preview, silent)
        return
    
    # Split long messages
    for i in range(0, len(text), MAX_LEN):
        part = text[i:i+MAX_LEN]
        _send_telegram(part, chat_id, token, parse_mode, disable_preview, silent)

class Watcher():
    running = True

    def __init__(self, currency = ["divine", "chaos", "divines"], show_header=False, refresh_delay_secs=1):
        if show_header:
            self.header()
        self.refresh = refresh_delay_secs/10
        if len(currency) > 1:
            currency = "|".join(currency)
        self.pattern = r"(\d+)\s*({0})".format(currency)
        logging.info("Watcher initialized")
        
    def follow(self, logfile):
        logfile.seek(0,2)
        while True:
            line = logfile.readline()
            if not line:
                time.sleep(self.refresh)
                continue
            yield line

    def header(self, title="Watcher", corners="+", edge_length=25, pad_level=1, sections=1):
        edge = f"{corners}{'-'*edge_length}{corners}"
        middle = lambda fill: fill.center(edge_length, " ")
        padding = middle(" ")
        if pad_level > 1:
            padding = "\n".join((middle(" ") for _ in range(pad_level)))
        
        header_text = []
        for i in range(sections):
            header_text.extend([edge, padding, middle(title), padding])
            if i == sections-1:
                header_text.append(edge)
        
        logging.info("\n".join(header_text))

    def start(self, chat_id: str, token: str, log_path: Path):
        logging.info("Starting trade message watcher")
        while self.running:
            try:
                with open(log_path, "r", encoding='utf-8') as logfile:
                    loglines = self.follow(logfile)
                    for line in loglines:
                        if '@From' in line:
                            match = re.findall(self.pattern, line.split('(stash')[0])
                            if match:
                                trade_request = {
                                    'Trade Message': line.split(']')[1],
                                    'Item': 'N/A',
                                    'Sale Price': ' and '.join(map(lambda x:' '.join(x),match))
                                }
                                logging.info(f"Trade detected: {json.dumps(trade_request, indent=4)}")
                                data = '\n'.join(('**{0}** : {1}'.format(k,v) for k,v in trade_request.items()))
                                # Send via Telegram bot
                                try:
                                    send_message(data, chat_id=chat_id, token=token, parse_mode='MARKDOWN', disable_preview=True)
                                    logging.info("Message sent successfully")
                                except Exception as e:
                                    logging.error(f"Failed to send message: {e}")
            except Exception as e:
                logging.error(f"Error watching log file: {e}")
                time.sleep(5)  # Wait before retrying

def main():
    # Set up paths
    script_dir = Path(__file__).parent
    default_root = Path(os.getenv("LOCALAPPDATA", Path.home())) / "NavalisOracle"
    log_path = default_root / "agent.log"
    
    # Set up logging before anything else
    setup_logging(log_path)
    
    # Load environment variables from .env files
    _load_dotenv(script_dir / ".env")
    _load_dotenv(default_root / ".env")
    
    # Get configuration from environment variables
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT")
    client_log = Path(os.getenv("CLIENT_LOG", "Client.txt"))

    if not client_log.exists():
        logging.error(f"Client log file '{client_log}' does not exist.")
        sys.exit(1)

    if not all([token, chat_id]):
        logging.error("Missing required environment variables. Please set TG_TOKEN and TG_CHAT in .env file")
        sys.exit(1)

    logging.info(f"Starting watcher with client log: {client_log}")
    watcher = Watcher(show_header=True)
    watcher.start(str(chat_id), str(token), client_log)

if __name__ == "__main__":
    main()