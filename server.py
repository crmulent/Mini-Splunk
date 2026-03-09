"""
Indexer Server Application (Mini-Splunk Server)

Thread-per-Connection Model:
- Main listener thread accepts TCP connections on a defined port
- Each connection is immediately passed to a newly spawned worker thread
- Worker threads handle client commands: INGEST, QUERY, ADMIN operations
- All shared data access is protected by locks in the DataStorage module
"""

import socket
import threading
import sys
import logging
from time import sleep

from syslog_parser import SyslogParser
from data_storage import DataStorage, get_global_storage
from query_engine import QueryEngine
from protocol import MessageParser, ResponseFormatter


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(threadName)-12s] %(levelname)-8s %(message)s'
)
logger = logging.getLogger(__name__)


class SyslogIndexerServer:
    """
    Main Indexer Server for the Mini-Splunk system.
    
    Implements Thread-per-Connection model with worker threads for each client.
    """
    
    def __init__(self, host: str = 'localhost', port: int = 5514, max_clients: int = 10):
        """
        Initialize the indexer server.
        
        Args:
            host: Server host (default: localhost)
            port: Server port (default: 5514, standard syslog port)
            max_clients: Maximum concurrent clients (default: 10)
        """
        self.host = host
        self.port = port
        self.max_clients = max_clients
        
        # Shared storage across all worker threads
        self.storage = get_global_storage()
        
        # Query engine
        self.query_engine = QueryEngine(self.storage)
        
        # Server socket
        self.server_socket = None
        
        # Thread management
        self.running = False
        self.worker_threads = []
        self.main_thread = None
        self.shutdown_event = threading.Event()
    
    def start(self):
        """Start the indexer server in a separate thread."""
        self.running = True
        self.main_thread = threading.Thread(target=self._run_server, name="MainListener", daemon=False)
        self.main_thread.start()
        logger.info(f"Server started on {self.host}:{self.port}")
    
    def stop(self):
        """Stop the indexer server and cleanup resources."""
        self.running = False
        self.shutdown_event.set()
        
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        
        # Wait for worker threads
        for thread in self.worker_threads:
            if thread.is_alive():
                thread.join(timeout=2)
        
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2)
        
        logger.info("Server stopped")
    
    def _run_server(self):
        """
        Main server loop: Listen for connections and spawn worker threads.
        This is the Thread-per-Connection dispatcher.
        """
        try:
            # Create server socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to port
            self.server_socket.bind((self.host, self.port))
            
            # Listen for connections
            self.server_socket.listen(self.max_clients)
            logger.info(f"Listening on {self.host}:{self.port}")
            
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Set timeout for accept to allow graceful shutdown
                    self.server_socket.settimeout(1)
                    
                    # Accept client connection
                    client_socket, client_address = self.server_socket.accept()
                    
                    # Spawn worker thread for this client (Thread-per-Connection)
                    worker = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_address),
                        name=f"Worker-{client_address[0]}:{client_address[1]}",
                        daemon=True
                    )
                    worker.start()
                    self.worker_threads.append(worker)
                    
                    logger.info(f"New client connection from {client_address}")
                    
                    # Clean up finished threads
                    self.worker_threads = [t for t in self.worker_threads if t.is_alive()]
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Error accepting connection: {e}")
        
        except Exception as e:
            logger.error(f"Server error: {e}")
        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
    
    def _handle_client(self, client_socket: socket.socket, client_address: tuple):
        """
        Handle a single client connection.
        This runs in a worker thread.
        
        Args:
            client_socket: Connected client socket
            client_address: Client address tuple (host, port)
        """
        try:
            # Set socket timeout
            client_socket.settimeout(30)
            
            while self.running:
                try:
                    # Receive message from client
                    message = client_socket.recv(65536).decode('utf-8', errors='ignore')
                    
                    if not message:
                        logger.info(f"Client {client_address} disconnected")
                        break
                    
                    # Parse and process the message
                    response = self._process_message(message)
                    
                    # Send response back to client
                    client_socket.sendall(response.encode('utf-8'))
                
                except socket.timeout:
                    logger.debug(f"Socket timeout for client {client_address}")
                    break
                except Exception as e:
                    logger.error(f"Error handling client {client_address}: {e}")
                    error_response = ResponseFormatter.error_internal(str(e))
                    try:
                        client_socket.sendall(error_response.encode('utf-8'))
                    except:
                        pass
                    break
        
        except Exception as e:
            logger.error(f"Unexpected error with client {client_address}: {e}")
        
        finally:
            try:
                client_socket.close()
            except:
                pass
    
    def _process_message(self, message: str) -> str:
        """
        Process a client message and return a response.
        
        Args:
            message: Raw message from client
            
        Returns:
            Response string to send to client
        """
        try:
            message = message.strip()
            if not message:
                return ResponseFormatter.error_malformed()
            
            # Parse the message
            command_type, parts = MessageParser.parse_message(message)
            
            if not command_type:
                return ResponseFormatter.error_malformed()
            
            # Route to appropriate handler
            if command_type == "UPLOAD":
                return self._handle_ingest(parts, message)
            elif command_type == "QUERY":
                return self._handle_query(parts)
            elif command_type == "ADMIN":
                return self._handle_admin(parts)
            elif command_type == "HELP":
                return self._get_help()
            elif command_type == "INFO":
                return self._get_info()
            else:
                return ResponseFormatter.error_invalid_command(command_type)
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return ResponseFormatter.error_internal(str(e))
    
    def _handle_ingest(self, parts: list, full_message: str) -> str:
        """
        Handle UPLOAD command: ingest syslog file content.
        
        Format: UPLOAD|<filesize>|<content>
        """
        try:
            if len(parts) < 2:
                return ResponseFormatter.error_malformed()
            
            # Extract file content (everything after first two pipes)
            filesize_str = parts[0]
            content = '|'.join(parts[1:])
            
            if not filesize_str.isdigit():
                return ResponseFormatter.error_malformed()
            
            # Parse the syslog content
            logs = SyslogParser.parse_syslog_stream(content)
            
            if not logs:
                return ResponseFormatter.error_parse("No valid logs found")
            
            # Add logs to storage (thread-safe)
            self.storage.add_logs(logs)
            
            logger.info(f"Ingested {len(logs)} logs")
            return ResponseFormatter.success_ingest(len(logs))
        
        except Exception as e:
            logger.error(f"Ingest error: {e}")
            return ResponseFormatter.error_io(str(e))
    
    def _handle_query(self, parts: list) -> str:
        """
        Handle QUERY command: search logs.
        
        Format: QUERY|<SEARCH_TYPE>|<PARAMETER>
        """
        try:
            if len(parts) < 2:
                return ResponseFormatter.error_malformed()
            
            search_type = parts[0].upper()
            search_param = '|'.join(parts[1:])  # Handle pipes in parameter
            
            # Execute appropriate search
            if search_type == "SEARCH_DATE":
                logs = self.query_engine.search_date(search_param)
            elif search_type == "SEARCH_HOST":
                logs = self.query_engine.search_host(search_param)
            elif search_type == "SEARCH_DAEMON":
                logs = self.query_engine.search_daemon(search_param)
            elif search_type == "SEARCH_SEVERITY":
                logs = self.query_engine.search_severity(search_param)
            elif search_type == "SEARCH_KEYWORD":
                logs = self.query_engine.search_keyword(search_param)
            elif search_type == "COUNT_KEYWORD":
                count = self.query_engine.count_keyword(search_param)
                return ResponseFormatter.success_count(count)
            else:
                return ResponseFormatter.error_invalid_command(f"QUERY|{search_type}")
            
            # Format logs for response
            logs_text = QueryEngine.format_logs_for_display(logs)
            return ResponseFormatter.success_query(logs_text)
        
        except Exception as e:
            logger.error(f"Query error: {e}")
            return ResponseFormatter.error_internal(str(e))
    
    def _handle_admin(self, parts: list) -> str:
        """
        Handle ADMIN command: administrative operations.
        
        Format: ADMIN|<OPERATION>
        """
        try:
            if len(parts) < 1:
                return ResponseFormatter.error_malformed()
            
            operation = parts[0].upper()
            
            if operation == "PURGE":
                self.storage.purge()
                logger.info("Database purged")
                return ResponseFormatter.success_purge()
            elif operation == "STATS":
                stats = self.query_engine.get_statistics()
                return ResponseFormatter.stats_response(stats)
            else:
                return ResponseFormatter.error_invalid_command(f"ADMIN|{operation}")
        
        except Exception as e:
            logger.error(f"Admin error: {e}")
            return ResponseFormatter.error_internal(str(e))
    
    def _get_help(self) -> str:
        """Return help information."""
        help_text = """
SUPPORTED COMMANDS:
  UPLOAD|<filesize>|<content>        - Ingest syslog file content
  QUERY|SEARCH_DATE|<date>           - Search logs by date (e.g., "Feb 22")
  QUERY|SEARCH_HOST|<hostname>       - Search logs by hostname
  QUERY|SEARCH_DAEMON|<daemon>       - Search logs by daemon name
  QUERY|SEARCH_SEVERITY|<level>      - Search logs by severity
  QUERY|SEARCH_KEYWORD|<word>        - Search logs by keyword in message
  QUERY|COUNT_KEYWORD|<word>         - Count keyword occurrences
  ADMIN|PURGE                        - Clear all logs from database
  ADMIN|STATS                        - Get database statistics
  HELP                               - Show this help message
  INFO                               - Show server information
"""
        return f"INFO|{help_text}"
    
    def _get_info(self) -> str:
        """Return server information."""
        stats = self.query_engine.get_statistics()
        info = f"""
Mini-Splunk Indexer Server
Listening on {self.host}:{self.port}
Total Logs: {stats['total_logs']}
Unique Hosts: {stats['unique_hosts']}
Unique Daemons: {stats['unique_daemons']}
"""
        return f"INFO|{info}"


def main():
    """Main entry point for the server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mini-Splunk Indexer Server")
    parser.add_argument('--host', default='localhost', help='Server host (default: localhost)')
    parser.add_argument('--port', type=int, default=5514, help='Server port (default: 5514)')
    parser.add_argument('--workers', type=int, default=10, help='Max concurrent clients (default: 10)')
    
    args = parser.parse_args()
    
    # Create and start server
    server = SyslogIndexerServer(host=args.host, port=args.port, max_clients=args.workers)
    server.start()
    
    try:
        # Keep server running
        while True:
            sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down server...")
        server.stop()
        logger.info("Server shutdown complete")


if __name__ == "__main__":
    main()
