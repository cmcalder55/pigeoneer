"""CLI entrypoint for Pigeoneer."""
import sys
from .watcher import Watcher

def main():
    """Main entry point for the Pigeoneer CLI."""
    try:
        watcher = Watcher(show_header=True)
        watcher.run()
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
