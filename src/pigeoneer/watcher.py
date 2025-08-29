"""Trade message watcher implementation."""
import re
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, List
from .telegram import send_message

class Watcher:
    """Watch Path of Exile log files for trade messages and send notifications."""
    
    def __init__(self, currency: List[str] = ["divine", "chaos", "divines"], 
                 show_header: bool = False, refresh_delay_secs: float = 1):
        if show_header:
            self.header()
        self.refresh = refresh_delay_secs/10
        self.pattern = r"(\d+)\s*({0})".format("|".join(currency))
        self.running = True
        self.watchers = []
        logging.info("Watcher initialized")
        
    def follow(self, logfile):
        """Generator that yields new lines from a file, similar to 'tail -f'."""
        logfile.seek(0,2)
        while True:
            line = logfile.readline()
            if not line:
                time.sleep(self.refresh)
                continue
            yield line

    def header(self, title="Watcher", corners="+", edge_length=25, pad_level=1, sections=1):
        """Print a formatted header to the log."""
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

    def watch_file(self, chat_id: str, token: str, log_path: Path, game_id: int):
        """Watch a single file for trade messages."""
        logging.info(f"Starting watcher for: {log_path}")
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
                                logging.info(f"[ PoE {game_id} ] Trade Request: {json.dumps(trade_request, indent=4)}")
                                data = '\n'.join(('**{0}** : {1}'.format(k,v) for k,v in trade_request.items()))
                                try:
                                    send_message(data, chat_id=chat_id, token=token, parse_mode='MARKDOWN', disable_preview=True)
                                    logging.info(f"Message sent successfully.\n")
                                except Exception as e:
                                    logging.error(f"Failed to send message for {log_path.name}: {e}\n")
            except Exception as e:
                logging.error(f"Error watching log file {log_path}: {e}")
                time.sleep(5)  # Wait before retrying

    def run(self):
        """Main entry point to start the watcher."""
        from .config import get_app_paths, load_dotenv, setup_logging
        import os
        
        # Set up paths and logging
        script_dir, env_file, log_path = get_app_paths()
        setup_logging(log_path)
        
        # Load configuration
        if not env_file.exists():
            logging.error(f".env file not found in {script_dir}")
            return 1
            
        load_dotenv(env_file)
        
        # Get configuration from environment variables
        token = os.getenv("TG_TOKEN")
        chat_id = os.getenv("TG_CHAT")
        
        # Check numbered client logs (CLIENT_LOG1, CLIENT_LOG2, etc.)
        game_client_logs = {
            1: Path(os.getenv("CLIENT_LOG_POE1", "Client.txt")),
            2: Path(os.getenv("CLIENT_LOG_POE2", "Client.txt"))
        }
        
        # Validate configuration
        valid_logs = {id: path for id, path in game_client_logs.items() if path.exists()}
        
        if not valid_logs:
            logging.error("No valid client log files found.")
            return 1

        if not all([token, chat_id]):
            logging.error("Missing required environment variables. Please set TG_TOKEN and TG_CHAT in .env file")
            return 1

        # Start watching logs
        logging.info(f"Starting watcher with client logs: {', '.join(str(p) for p in valid_logs.values())}")
        self.start(str(chat_id), str(token), valid_logs)
        return 0

    def start(self, chat_id: str, token: str, log_paths: Dict[int, Path]):
        """Start watching multiple files in separate threads."""
        logging.info(f"Starting trade message watcher for {len(log_paths)} files")
        
        # Create and start a thread for each file
        for game_id, log_path in log_paths.items():
            if not log_path.exists():
                logging.error(f"Log file does not exist: {log_path}")
                continue

            thread = threading.Thread(
                target=self.watch_file,
                args=(chat_id, token, log_path, game_id),
                name=f"Watcher-{log_path.name}",
                daemon=True
            )
            self.watchers.append(thread)
            thread.start()
        
        # Wait for all watchers to finish (they won't unless self.running is set to False)
        try:
            while any(w.is_alive() for w in self.watchers):
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info("Shutting down watchers...")
            self.running = False
            for w in self.watchers:
                w.join(timeout=5)
