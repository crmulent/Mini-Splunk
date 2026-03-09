"""
Query Engine Module
Houses the search and filter functions for querying indexed logs.
Supports: DATE, HOST, DAEMON, SEVERITY, KEYWORD searches and COUNT operations.
"""

from typing import List, Dict, Optional
from data_storage import DataStorage


class QueryEngine:
    """
    Query engine for searching and filtering logs.
    
    Implements operations:
    - SEARCH_DATE: Filter by date
    - SEARCH_HOST: Filter by hostname
    - SEARCH_DAEMON: Filter by daemon
    - SEARCH_SEVERITY: Filter by severity level
    - SEARCH_KEYWORD: Filter by keyword in message
    - COUNT_KEYWORD: Count occurrences of keyword
    """
    
    def __init__(self, storage: DataStorage):
        """
        Initialize query engine with a data storage instance.
        
        Args:
            storage: DataStorage instance to query
        """
        self.storage = storage
    
    def search_date(self, date: str) -> List[Dict]:
        """
        Search logs by date.
        
        Args:
            date: Date string in format "Feb 22" or "Feb 22 00:05:38"
            
        Returns:
            List of matching logs
        """
        logs = self.storage.get_all_logs()
        return [log for log in logs if date.lower() in log.get('timestamp', '').lower()]
    
    def search_host(self, hostname: str) -> List[Dict]:
        """
        Search logs by hostname.
        
        Args:
            hostname: Hostname to search for
            
        Returns:
            List of logs from specified host
        """
        logs = self.storage.get_all_logs()
        return [log for log in logs if log.get('hostname', '').lower() == hostname.lower()]
    
    def search_daemon(self, daemon: str) -> List[Dict]:
        """
        Search logs by daemon name.
        
        Args:
            daemon: Daemon name to search for
            
        Returns:
            List of logs from specified daemon
        """
        logs = self.storage.get_all_logs()
        return [log for log in logs if log.get('daemon', '').lower() == daemon.lower()]
    
    def search_severity(self, severity: str) -> List[Dict]:
        """
        Search logs by severity level.
        
        Args:
            severity: Severity level (EMERG, ALERT, CRIT, ERR, WARNING, NOTICE, INFO, DEBUG)
            
        Returns:
            List of logs with specified severity
        """
        logs = self.storage.get_all_logs()
        severity_upper = severity.upper()
        return [log for log in logs if log.get('severity', '').upper() == severity_upper]
    
    def search_keyword(self, keyword: str) -> List[Dict]:
        """
        Search logs by keyword in message.
        
        Args:
            keyword: Keyword to search for in message
            
        Returns:
            List of logs containing the keyword
        """
        logs = self.storage.get_all_logs()
        keyword_lower = keyword.lower()
        return [log for log in logs if keyword_lower in log.get('message', '').lower()]
    
    def count_keyword(self, keyword: str) -> int:
        """
        Count occurrences of keyword in messages.
        
        Args:
            keyword: Keyword to count
            
        Returns:
            Number of log entries containing the keyword
        """
        logs = self.search_keyword(keyword)
        return len(logs)
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the log database.
        
        Returns:
            Dictionary with statistics
        """
        logs = self.storage.get_all_logs()
        
        # Count unique values
        hosts = set(log.get('hostname', '') for log in logs)
        daemons = set(log.get('daemon', '') for log in logs)
        severities = set(log.get('severity', '') for log in logs)
        
        # Count by severity
        severity_counts = {}
        for log in logs:
            severity = log.get('severity', 'UNKNOWN')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        
        return {
            'total_logs': len(logs),
            'unique_hosts': len(hosts),
            'unique_daemons': len(daemons),
            'unique_severities': len(severities),
            'logs_by_severity': severity_counts,
            'hosts': sorted(list(hosts)),
            'daemons': sorted(list(daemons)),
        }
    
    @staticmethod
    def format_logs_for_display(logs: List[Dict]) -> str:
        """
        Format logs as a human-readable string.
        
        Args:
            logs: List of log dictionaries
            
        Returns:
            Formatted string representation
        """
        if not logs:
            return "No logs found."
        
        lines = []
        for i, log in enumerate(logs, 1):
            formatted = (
                f"{i}. [{log.get('timestamp', 'N/A')}] "
                f"Host: {log.get('hostname', 'N/A')} | "
                f"Daemon: {log.get('daemon', 'N/A')} | "
                f"Severity: {log.get('severity', 'N/A')} | "
                f"Msg: {log.get('message', 'N/A')[:100]}"
            )
            lines.append(formatted)
        
        return '\n'.join(lines)


# For testing
if __name__ == "__main__":
    from data_storage import DataStorage
    
    storage = DataStorage()
    engine = QueryEngine(storage)
    
    # Add test data
    test_logs = [
        {"timestamp": "Feb 22 00:05:38", "hostname": "SYSSVR1", "daemon": "systemd", "severity": "INFO", "message": "Service started"},
        {"timestamp": "Feb 22 00:06:00", "hostname": "SYSSVR2", "daemon": "kernel", "severity": "WARNING", "message": "Low memory condition"},
        {"timestamp": "Feb 22 00:07:15", "hostname": "SYSSVR1", "daemon": "httpd", "severity": "INFO", "message": "Request processed"},
    ]
    
    storage.add_logs(test_logs)
    
    # Test queries
    print("Search by host SYSSVR1:")
    print(QueryEngine.format_logs_for_display(engine.search_host("SYSSVR1")))
    print()
    
    print("Search by severity WARNING:")
    print(QueryEngine.format_logs_for_display(engine.search_severity("WARNING")))
    print()
    
    print("Search by keyword 'memory':")
    print(QueryEngine.format_logs_for_display(engine.search_keyword("memory")))
    print()
    
    print("Statistics:")
    print(engine.get_statistics())
