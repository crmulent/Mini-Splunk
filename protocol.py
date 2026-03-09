"""
Protocol Definitions Module
Defines the TCP communication protocol between client and server.
"""


class ProtocolCommands:
    """
    Protocol command definitions and message formats.
    
    All messages follow the pattern: COMMAND_TYPE|PARAM1|PARAM2|...
    """
    
    # Ingest operations
    INGEST_PREFIX = "UPLOAD"
    INGEST_FORMAT = "UPLOAD|{filesize}|{content}"
    # Example: UPLOAD|1024|<file_content_stream>
    
    # Query operations
    QUERY_PREFIX = "QUERY"
    
    QUERY_DATE = "QUERY|SEARCH_DATE|{date}"
    QUERY_HOST = "QUERY|SEARCH_HOST|{hostname}"
    QUERY_DAEMON = "QUERY|SEARCH_DAEMON|{daemon}"
    QUERY_SEVERITY = "QUERY|SEARCH_SEVERITY|{level}"
    QUERY_KEYWORD = "QUERY|SEARCH_KEYWORD|{keyword}"
    QUERY_COUNT = "QUERY|COUNT_KEYWORD|{keyword}"
    
    # Administrative operations
    ADMIN_PREFIX = "ADMIN"
    ADMIN_PURGE = "ADMIN|PURGE"
    ADMIN_STATS = "ADMIN|STATS"
    
    # Help and info
    HELP_REQUEST = "HELP"
    INFO_REQUEST = "INFO"


class ProtocolResponses:
    """
    Protocol response definitions.
    Server responses follow specific formats for different commands.
    """
    
    # Success responses
    SUCCESS_INGEST = "SUCCESS|INGEST|{count} logs ingested"
    SUCCESS_QUERY = "SUCCESS|QUERY|{result}"
    SUCCESS_PURGE = "SUCCESS|PURGE|All logs cleared"
    SUCCESS_COUNT = "SUCCESS|COUNT|{count}"
    
    # Error responses
    ERROR_PARSE = "ERROR|PARSE|Failed to parse log entry"
    ERROR_INVALID_COMMAND = "ERROR|INVALID_COMMAND|Unknown command: {command}"
    ERROR_MALFORMED = "ERROR|MALFORMED|Message format is incorrect"
    ERROR_IO = "ERROR|IO|File I/O error: {details}"
    ERROR_INTERNAL = "ERROR|INTERNAL|Server error: {details}"
    
    # Info responses
    INFO_RESPONSE = "INFO|{info}"
    STATS_RESPONSE = "STATS|{stats}"


class MessageParser:
    """
    Utility class for parsing and validating protocol messages.
    """
    
    @staticmethod
    def parse_message(message: str) -> tuple:
        """
        Parse a protocol message into components.
        
        Args:
            message: Raw message string
            
        Returns:
            Tuple of (command_type, components)
        """
        parts = message.split('|')
        if not parts:
            return None, None
        
        command_type = parts[0].upper()
        return command_type, parts[1:] if len(parts) > 1 else []
    
    @staticmethod
    def validate_ingest_message(parts: list) -> bool:
        """Validate UPLOAD message format."""
        return len(parts) >= 2 and parts[0].isdigit()
    
    @staticmethod
    def validate_query_message(parts: list) -> bool:
        """Validate QUERY message format."""
        return len(parts) >= 2 and parts[0] in [
            'SEARCH_DATE', 'SEARCH_HOST', 'SEARCH_DAEMON',
            'SEARCH_SEVERITY', 'SEARCH_KEYWORD', 'COUNT_KEYWORD'
        ]
    
    @staticmethod
    def validate_admin_message(parts: list) -> bool:
        """Validate ADMIN message format."""
        return len(parts) >= 1 and parts[0] in ['PURGE', 'STATS']


class ResponseFormatter:
    """
    Utility class for formatting server responses.
    """
    
    @staticmethod
    def success_ingest(count: int) -> str:
        """Format successful ingest response."""
        return f"SUCCESS|INGEST|{count} logs ingested"
    
    @staticmethod
    def success_query(logs_text: str) -> str:
        """Format successful query response."""
        return f"SUCCESS|QUERY|{logs_text}"
    
    @staticmethod
    def success_count(count: int) -> str:
        """Format successful count response."""
        return f"SUCCESS|COUNT|{count}"
    
    @staticmethod
    def success_purge() -> str:
        """Format successful purge response."""
        return "SUCCESS|PURGE|All logs cleared"
    
    @staticmethod
    def error_invalid_command(command: str) -> str:
        """Format invalid command error."""
        return f"ERROR|INVALID_COMMAND|Unknown command: {command}"
    
    @staticmethod
    def error_malformed() -> str:
        """Format malformed message error."""
        return "ERROR|MALFORMED|Message format is incorrect"
    
    @staticmethod
    def error_parse(details: str = "") -> str:
        """Format parse error."""
        if details:
            return f"ERROR|PARSE|Failed to parse log entry: {details}"
        return "ERROR|PARSE|Failed to parse log entry"
    
    @staticmethod
    def error_io(details: str = "") -> str:
        """Format I/O error."""
        return f"ERROR|IO|File I/O error: {details}"
    
    @staticmethod
    def error_internal(details: str = "") -> str:
        """Format internal error."""
        return f"ERROR|INTERNAL|Server error: {details}"
    
    @staticmethod
    def stats_response(stats_dict: dict) -> str:
        """Format statistics response."""
        stats_str = ' | '.join([f"{k}: {v}" for k, v in stats_dict.items()])
        return f"STATS|{stats_str}"


# For testing
if __name__ == "__main__":
    # Test message parsing
    msg1 = "UPLOAD|1024|content_here"
    cmd, parts = MessageParser.parse_message(msg1)
    print(f"Parsed: {cmd}, {parts}")
    
    msg2 = "QUERY|SEARCH_DATE|Feb 22"
    cmd, parts = MessageParser.parse_message(msg2)
    print(f"Parsed: {cmd}, {parts}")
    
    # Test response formatting
    response = ResponseFormatter.success_ingest(42)
    print(f"Response: {response}")
    
    response2 = ResponseFormatter.success_count(13)
    print(f"Response: {response2}")
