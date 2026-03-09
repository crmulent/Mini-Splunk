"""
RFC 3164 Syslog Parser Module
Converts raw syslog strings into structured dictionaries
"""

import re
from datetime import datetime
from typing import Optional, Dict


class SyslogParser:
    """
    Parses RFC 3164 standard syslog format.
    
    Format: <PRI>MMM DD HH:MM:SS HOSTNAME TAG[PID]: MSG
    Example: <134>Feb 22 00:05:38 SYSSVR1 systemd: Started OpenBSD Secure Shell server...
    """
    
    # RFC 3164 syslog regex pattern
    # Pattern: <PRI>MMM DD HH:MM:SS HOSTNAME DAEMON[PID]: MESSAGE
    SYSLOG_PATTERN = re.compile(
        r'^(?:<(\d+)>)?'                           # Priority (optional)
        r'(\w+\s+\d+\s+\d{2}:\d{2}:\d{2})\s+'     # Timestamp (MMM DD HH:MM:SS)
        r'(\S+)\s+'                                 # Hostname
        r'(\w+)(?:\[(\d+)\])?:'                    # Daemon and optional PID (colon required)
        r'\s*(.*)$'                                 # Message
    )
    
    # Severity levels (RFC 3164)
    SEVERITY_LEVELS = {
        0: 'EMERG',
        1: 'ALERT',
        2: 'CRIT',
        3: 'ERR',
        4: 'WARNING',
        5: 'NOTICE',
        6: 'INFO',
        7: 'DEBUG'
    }
    
    # Month name to number mapping
    MONTH_MAP = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    @staticmethod
    def parse_syslog(syslog_line: str, year: int = 2026) -> Optional[Dict]:
        """
        Parse a single syslog line into a structured dictionary.
        
        Args:
            syslog_line: Raw syslog string
            year: Year to use for timestamp (default: current year)
            
        Returns:
            Dictionary with keys: timestamp, hostname, daemon, severity, message
            Returns None if parsing fails
        """
        if not syslog_line or not syslog_line.strip():
            return None
        
        match = re.match(SyslogParser.SYSLOG_PATTERN, syslog_line.strip())
        if not match:
            return None
        
        priority_str, timestamp_str, hostname, daemon, pid, message = match.groups()
        
        # Handle optional components
        message = message.strip()
        
        # Determine severity from priority (RFC 3164)
        severity = "INFO"  # default
        if priority_str:
            try:
                priority = int(priority_str)
                severity_code = priority & 0x07  # Lower 3 bits
                severity = SyslogParser.SEVERITY_LEVELS.get(severity_code, "INFO")
            except ValueError:
                pass
        
        # Parse timestamp
        # Handle timestamp parsing (e.g., "Feb 22 00:05:38")
        try:
            timestamp = SyslogParser._parse_timestamp(timestamp_str, year)
        except (ValueError, AttributeError):
            timestamp = timestamp_str  # Keep original if parsing fails
        
        return {
            "timestamp": timestamp,
            "hostname": hostname,
            "daemon": daemon,
            "severity": severity,
            "message": message
        }
    
    @staticmethod
    def _parse_timestamp(timestamp_str: str, year: int) -> str:
        """Parse RFC 3164 timestamp format: MMM DD HH:MM:SS"""
        parts = timestamp_str.split()
        if len(parts) < 3:
            return timestamp_str
        
        month_str, day_str, time_str = parts[0], parts[1], parts[2]
        
        month = SyslogParser.MONTH_MAP.get(month_str, 1)
        day = int(day_str)
        hour, minute, second = map(int, time_str.split(':'))
        
        dt = datetime(year, month, day, hour, minute, second)
        return dt.strftime("%b %d %H:%M:%S")
    
    @staticmethod
    def parse_syslog_file(file_path: str) -> list:
        """
        Parse an entire syslog file.
        
        Args:
            file_path: Path to syslog file
            
        Returns:
            List of parsed log dictionaries
        """
        logs = []
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = SyslogParser.parse_syslog(line)
                    if parsed:
                        logs.append(parsed)
        except IOError as e:
            raise IOError(f"Failed to read syslog file: {e}")
        
        return logs
    
    @staticmethod
    def parse_syslog_stream(content: str) -> list:
        """
        Parse syslog content from a stream/string.
        
        Args:
            content: Syslog content as string
            
        Returns:
            List of parsed log dictionaries
        """
        logs = []
        for line in content.split('\n'):
            parsed = SyslogParser.parse_syslog(line)
            if parsed:
                logs.append(parsed)
        
        return logs


# For testing
if __name__ == "__main__":
    test_log = "<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Started OpenBSD Secure Shell server."
    parsed = SyslogParser.parse_syslog(test_log)
    print("Parsed log:", parsed)
    
    test_log2 = "Feb 22 00:05:38 SYSSVR1 kernel: Out of memory"
    parsed2 = SyslogParser.parse_syslog(test_log2)
    print("Parsed log 2:", parsed2)
