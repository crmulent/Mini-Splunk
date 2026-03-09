"""
Forwarder Client Application (Mini-Splunk Client)

CLI client for interacting with the Mini-Splunk Indexer Server.
Handles:
- Parsing user commands
- Reading local syslog files
- Establishing TCP connections to server
- Rendering server responses
"""

import socket
import sys
import os
import argparse
from pathlib import Path


class SyslogForwarderClient:
    """
    CLI Client for Mini-Splunk indexer server.
    
    Responsible for:
    - Parsing user commands
    - Reading local syslog files
    - Establishing TCP connections
    - Rendering server responses
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5514, timeout: int = 30):
        """
        Initialize the forwarder client.
        
        Args:
            host: Server host
            port: Server port
            timeout: Socket timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket = None
    
    def connect(self) -> bool:
        """
        Establish connection to the indexer server.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            print(f"✓ Connected to server at {self.host}:{self.port}")
            return True
        except socket.error as e:
            print(f"✗ Failed to connect: {e}", file=sys.stderr)
            return False
    
    def disconnect(self):
        """Close connection to server."""
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
    
    def send_command(self, command: str) -> bool:
        """
        Send a command to the server.
        
        Args:
            command: Command string to send
            
        Returns:
            True if successful
        """
        try:
            if not self.socket:
                print("✗ Not connected to server", file=sys.stderr)
                return False
            
            self.socket.sendall(command.encode('utf-8'))
            return True
        except socket.error as e:
            print(f"✗ Send error: {e}", file=sys.stderr)
            return False
    
    def receive_response(self) -> str:
        """
        Receive response from the server.
        
        Returns:
            Response string from server
        """
        try:
            if not self.socket:
                return ""
            
            response = self.socket.recv(65536).decode('utf-8', errors='ignore')
            return response
        except socket.error as e:
            print(f"✗ Receive error: {e}", file=sys.stderr)
            return ""
    
    def ingest_file(self, file_path: str) -> bool:
        """
        Read a syslog file and send it to the server.
        
        Args:
            file_path: Path to syslog file
            
        Returns:
            True if successful
        """
        try:
            # Check if file exists
            if not os.path.isfile(file_path):
                print(f"✗ File not found: {file_path}", file=sys.stderr)
                return False
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            file_size = len(content.encode('utf-8'))
            
            # Create UPLOAD command
            command = f"UPLOAD|{file_size}|{content}"
            
            print(f"→ Uploading {file_size} bytes from {file_path}...")
            
            # Send to server
            if not self.send_command(command):
                return False
            
            # Receive response
            response = self.receive_response()
            
            # Process response
            return self._process_response(response)
        
        except IOError as e:
            print(f"✗ File read error: {e}", file=sys.stderr)
            return False
    
    def search_date(self, date: str) -> bool:
        """Search logs by date."""
        command = f"QUERY|SEARCH_DATE|{date}"
        return self._send_query(command, f"Searching logs for date: {date}")
    
    def search_host(self, hostname: str) -> bool:
        """Search logs by hostname."""
        command = f"QUERY|SEARCH_HOST|{hostname}"
        return self._send_query(command, f"Searching logs for host: {hostname}")
    
    def search_daemon(self, daemon: str) -> bool:
        """Search logs by daemon."""
        command = f"QUERY|SEARCH_DAEMON|{daemon}"
        return self._send_query(command, f"Searching logs for daemon: {daemon}")
    
    def search_severity(self, severity: str) -> bool:
        """Search logs by severity."""
        command = f"QUERY|SEARCH_SEVERITY|{severity}"
        return self._send_query(command, f"Searching logs for severity: {severity}")
    
    def search_keyword(self, keyword: str) -> bool:
        """Search logs by keyword."""
        command = f"QUERY|SEARCH_KEYWORD|{keyword}"
        return self._send_query(command, f"Searching logs for keyword: '{keyword}'")
    
    def count_keyword(self, keyword: str) -> bool:
        """Count keyword occurrences."""
        command = f"QUERY|COUNT_KEYWORD|{keyword}"
        return self._send_query(command, f"Counting occurrences of '{keyword}'")
    
    def purge_logs(self) -> bool:
        """Clear all logs from server."""
        command = "ADMIN|PURGE"
        print("→ Purging all logs from server...")
        
        if not self.send_command(command):
            return False
        
        response = self.receive_response()
        return self._process_response(response)
    
    def get_stats(self) -> bool:
        """Get server statistics."""
        command = "ADMIN|STATS"
        print("→ Requesting server statistics...")
        
        if not self.send_command(command):
            return False
        
        response = self.receive_response()
        return self._process_response(response)
    
    def get_help(self) -> bool:
        """Get help information."""
        command = "HELP"
        
        if not self.send_command(command):
            return False
        
        response = self.receive_response()
        return self._process_response(response)
    
    def _send_query(self, command: str, description: str) -> bool:
        """
        Send a query command and process response.
        
        Args:
            command: Query command to send
            description: Description of query
            
        Returns:
            True if successful
        """
        print(f"→ {description}...")
        
        if not self.send_command(command):
            return False
        
        response = self.receive_response()
        return self._process_response(response)
    
    def _process_response(self, response: str) -> bool:
        """
        Process server response and display results.
        
        Args:
            response: Response string from server
            
        Returns:
            True if response indicates success
        """
        if not response:
            print("✗ No response from server", file=sys.stderr)
            return False
        
        # Parse response
        parts = response.split('|', 2)
        status = parts[0] if parts else ""
        
        if status == "SUCCESS":
            if len(parts) > 2:
                result = parts[2]
                print(f"✓ {result}")
            else:
                print("✓ Operation successful")
            return True
        
        elif status == "ERROR":
            error_type = parts[1] if len(parts) > 1 else "UNKNOWN"
            error_msg = parts[2] if len(parts) > 2 else ""
            print(f"✗ Error ({error_type}): {error_msg}", file=sys.stderr)
            return False
        
        elif status == "INFO" or status == "STATS":
            if len(parts) > 1:
                info = parts[1]
                print(info)
            return True
        
        else:
            # Unknown response, print as-is
            print(response)
            return True


def print_help():
    """Print help information for interactive mode."""
    help_text = """
AVAILABLE COMMANDS:
  ingest <filepath>          - Upload and ingest a syslog file
  search host <hostname>     - Search logs by hostname
  search date <date>         - Search logs by date (e.g., "Feb 22")
  search daemon <daemon>     - Search logs by daemon name
  search severity <level>    - Search logs by severity (INFO, WARNING, ERR, etc.)
  search keyword <word>      - Search logs containing keyword
  count <keyword>            - Count occurrences of keyword
  stats                      - Show database statistics
  purge                      - Clear all logs from database
  help                       - Show this help message
  quit                       - Exit the client

EXAMPLES:
  ingest sample_logs.txt
  search host SYSSVR1
  search keyword error
  count failed
"""
    print(help_text)


def interactive_mode(client: SyslogForwarderClient):
    """
    Run the client in interactive mode.
    
    Args:
        client: SyslogForwarderClient instance
    """
    print("\n" + "="*60)
    print("Mini-Splunk Forwarder Client - Interactive Mode")
    print("="*60)
    print("Type 'help' for available commands, 'quit' to exit\n")
    
    while True:
        try:
            user_input = input("splunk> ").strip()
            
            if not user_input:
                continue
            
            # Parse user command - support both "search host" and "search-host" formats
            tokens = user_input.split()
            command = tokens[0].lower()
            
            # Handle two-word commands like "search host SYSSVR1"
            if command == "search" and len(tokens) >= 2:
                subcommand = tokens[1].lower()
                arg = ' '.join(tokens[2:]) if len(tokens) > 2 else ""
                command = f"search-{subcommand}"
            elif command == "count" and len(tokens) >= 2:
                arg = ' '.join(tokens[1:]) if len(tokens) > 1 else ""
                command = "count-keyword"
            else:
                arg = ' '.join(tokens[1:]) if len(tokens) > 1 else ""
            
            # Route to appropriate handler
            if command == "quit" or command == "exit":
                print("Disconnecting...")
                break
            
            elif command == "help":
                print_help()
            
            elif command == "ingest":
                if not arg:
                    print("Usage: ingest <filepath>")
                else:
                    client.ingest_file(arg)
            
            elif command == "search-date" or command == "search-d":
                if not arg:
                    print("Usage: search date <date>")
                else:
                    client.search_date(arg)
            
            elif command == "search-host" or command == "search-h":
                if not arg:
                    print("Usage: search host <hostname>")
                else:
                    client.search_host(arg)
            
            elif command == "search-daemon":
                if not arg:
                    print("Usage: search daemon <daemon>")
                else:
                    client.search_daemon(arg)
            
            elif command == "search-severity" or command == "search-s":
                if not arg:
                    print("Usage: search severity <level>")
                else:
                    client.search_severity(arg)
            
            elif command == "search-keyword" or command == "search-k":
                if not arg:
                    print("Usage: search keyword <keyword>")
                else:
                    client.search_keyword(arg)
            
            elif command == "count-keyword" or command == "count":
                if not arg:
                    print("Usage: count <keyword>")
                else:
                    client.count_keyword(arg)
            
            elif command == "purge":
                if input("Are you sure? (yes/no): ").lower() == "yes":
                    client.purge_logs()
            
            elif command == "stats":
                client.get_stats()
            
            else:
                print(f"Unknown command: {command}. Type 'help' for available commands.")
        
        except KeyboardInterrupt:
            print("\nInterrupted. Disconnecting...")
            break
        except EOFError:
            break
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)


def main():
    """Main entry point for the client."""
    parser = argparse.ArgumentParser(description="Mini-Splunk Forwarder Client")
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=5514, help='Server port (default: 5514)')
    parser.add_argument('--timeout', type=int, default=30, help='Socket timeout in seconds (default: 30)')
    
    # Optional command to execute
    parser.add_argument('command', nargs='?', help='Command to execute')
    parser.add_argument('args', nargs='*', help='Command arguments')
    
    args = parser.parse_args()
    
    # Create client
    client = SyslogForwarderClient(host=args.host, port=args.port, timeout=args.timeout)
    
    # Connect to server
    if not client.connect():
        sys.exit(1)
    
    try:
        if args.command:
            # Execute single command
            command = args.command.lower()
            command_args = ' '.join(args.args)
            
            if command == "ingest":
                client.ingest_file(command_args)
            elif command == "search-date":
                client.search_date(command_args)
            elif command == "search-host":
                client.search_host(command_args)
            elif command == "search-daemon":
                client.search_daemon(command_args)
            elif command == "search-severity":
                client.search_severity(command_args)
            elif command == "search-keyword":
                client.search_keyword(command_args)
            elif command == "count-keyword":
                client.count_keyword(command_args)
            elif command == "purge":
                client.purge_logs()
            elif command == "stats":
                client.get_stats()
            elif command == "help":
                client.get_help()
            else:
                print(f"Unknown command: {command}")
        else:
            # Interactive mode
            interactive_mode(client)
    
    finally:
        client.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    main()
