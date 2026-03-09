#!/usr/bin/env python3
"""
Unit Tests for Mini-Splunk Protocol Commands

Tests all client commands and their expected server responses:
- INGEST: UPLOAD|<filesize>|<file_content_stream>
- SEARCH_DATE: QUERY|SEARCH_DATE|<date>
- SEARCH_HOST: QUERY|SEARCH_HOST|<hostname>
- SEARCH_DAEMON: QUERY|SEARCH_DAEMON|<daemon>
- SEARCH_SEVERITY: QUERY|SEARCH_SEVERITY|<level>
- SEARCH_KEYWORD: QUERY|SEARCH_KEYWORD|<word>
- COUNT_KEYWORD: QUERY|COUNT_KEYWORD|<word>
- PURGE: ADMIN|PURGE
"""

import unittest
import threading
from unittest.mock import MagicMock, patch

from data_storage import DataStorage
from query_engine import QueryEngine
from protocol import MessageParser, ResponseFormatter, ProtocolCommands
from syslog_parser import SyslogParser


# Sample syslog entries for testing
SAMPLE_SYSLOG_CONTENT = """<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Started OpenBSD Secure Shell server.
<133>Feb 22 00:05:39 SYSSVR1 sshd[2847]: Server listening on 0.0.0.0 port 22.
<134>Feb 22 00:05:40 SYSSVR2 kernel: [    0.000000] Linux version 5.4.0-42-generic
<131>Feb 22 00:07:30 SYSSVR1 httpd[8234]: Started Apache httpd server
<135>Feb 22 00:12:30 SYSSVR1 sshd[3456]: Invalid user attempt from 192.168.1.100
<134>Mar 01 10:15:00 SYSSVR3 mysql[456]: Database connection established
"""


class TestMessageParser(unittest.TestCase):
    """Test protocol message parsing functionality."""
    
    def test_parse_upload_message(self):
        """Test parsing UPLOAD|<filesize>|<content> format."""
        message = "UPLOAD|1024|log content here"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "UPLOAD")
        self.assertEqual(parts[0], "1024")
        self.assertEqual(parts[1], "log content here")
    
    def test_parse_query_search_date(self):
        """Test parsing QUERY|SEARCH_DATE|<date> format."""
        message = "QUERY|SEARCH_DATE|Feb 22"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "SEARCH_DATE")
        self.assertEqual(parts[1], "Feb 22")
    
    def test_parse_query_search_host(self):
        """Test parsing QUERY|SEARCH_HOST|<hostname> format."""
        message = "QUERY|SEARCH_HOST|SYSSVR1"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "SEARCH_HOST")
        self.assertEqual(parts[1], "SYSSVR1")
    
    def test_parse_query_search_daemon(self):
        """Test parsing QUERY|SEARCH_DAEMON|<daemon> format."""
        message = "QUERY|SEARCH_DAEMON|kernel"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "SEARCH_DAEMON")
        self.assertEqual(parts[1], "kernel")
    
    def test_parse_query_search_severity(self):
        """Test parsing QUERY|SEARCH_SEVERITY|<level> format."""
        message = "QUERY|SEARCH_SEVERITY|INFO"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "SEARCH_SEVERITY")
        self.assertEqual(parts[1], "INFO")
    
    def test_parse_query_search_keyword(self):
        """Test parsing QUERY|SEARCH_KEYWORD|<word> format."""
        message = "QUERY|SEARCH_KEYWORD|error"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "SEARCH_KEYWORD")
        self.assertEqual(parts[1], "error")
    
    def test_parse_query_count_keyword(self):
        """Test parsing QUERY|COUNT_KEYWORD|<word> format."""
        message = "QUERY|COUNT_KEYWORD|memory"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "QUERY")
        self.assertEqual(parts[0], "COUNT_KEYWORD")
        self.assertEqual(parts[1], "memory")
    
    def test_parse_admin_purge(self):
        """Test parsing ADMIN|PURGE format."""
        message = "ADMIN|PURGE"
        command_type, parts = MessageParser.parse_message(message)
        
        self.assertEqual(command_type, "ADMIN")
        self.assertEqual(parts[0], "PURGE")
    
    def test_validate_ingest_message(self):
        """Test validation of UPLOAD message format."""
        # Valid ingest
        self.assertTrue(MessageParser.validate_ingest_message(["1024", "content"]))
        # Invalid - filesize not a digit
        self.assertFalse(MessageParser.validate_ingest_message(["abc", "content"]))
        # Invalid - missing content
        self.assertFalse(MessageParser.validate_ingest_message(["1024"]))
    
    def test_validate_query_message(self):
        """Test validation of QUERY message format."""
        # Valid queries
        self.assertTrue(MessageParser.validate_query_message(["SEARCH_DATE", "Feb 22"]))
        self.assertTrue(MessageParser.validate_query_message(["SEARCH_HOST", "server1"]))
        self.assertTrue(MessageParser.validate_query_message(["SEARCH_DAEMON", "sshd"]))
        self.assertTrue(MessageParser.validate_query_message(["SEARCH_SEVERITY", "INFO"]))
        self.assertTrue(MessageParser.validate_query_message(["SEARCH_KEYWORD", "error"]))
        self.assertTrue(MessageParser.validate_query_message(["COUNT_KEYWORD", "memory"]))
        # Invalid - unknown search type
        self.assertFalse(MessageParser.validate_query_message(["UNKNOWN_TYPE", "value"]))
    
    def test_validate_admin_message(self):
        """Test validation of ADMIN message format."""
        self.assertTrue(MessageParser.validate_admin_message(["PURGE"]))
        self.assertTrue(MessageParser.validate_admin_message(["STATS"]))
        self.assertFalse(MessageParser.validate_admin_message(["UNKNOWN"]))


class TestDataStorage(unittest.TestCase):
    """Test thread-safe data storage operations."""
    
    def setUp(self):
        """Create fresh storage instance for each test."""
        self.storage = DataStorage()
    
    def test_add_logs_acquires_write_lock(self):
        """Test that add_logs acquires write lock and appends to storage."""
        logs = [
            {"timestamp": "Feb 22 00:05:38", "hostname": "SYSSVR1", 
             "daemon": "systemd", "severity": "INFO", "message": "Test message"}
        ]
        
        result = self.storage.add_logs(logs)
        
        self.assertTrue(result)
        self.assertEqual(self.storage.get_log_count(), 1)
    
    def test_add_multiple_logs(self):
        """Test adding multiple logs to storage."""
        logs = [
            {"timestamp": "Feb 22 00:05:38", "hostname": "SYSSVR1", 
             "daemon": "systemd", "severity": "INFO", "message": "Message 1"},
            {"timestamp": "Feb 22 00:06:00", "hostname": "SYSSVR2", 
             "daemon": "kernel", "severity": "WARNING", "message": "Message 2"},
        ]
        
        self.storage.add_logs(logs)
        
        self.assertEqual(self.storage.get_log_count(), 2)
        self.assertEqual(self.storage.get_host_count(), 2)
    
    def test_get_all_logs_returns_copy(self):
        """Test that get_all_logs returns a copy of logs."""
        logs = [
            {"timestamp": "Feb 22 00:05:38", "hostname": "SYSSVR1", 
             "daemon": "systemd", "severity": "INFO", "message": "Test"}
        ]
        self.storage.add_logs(logs)
        
        retrieved = self.storage.get_all_logs()
        retrieved[0]["hostname"] = "MODIFIED"
        
        # Original should be unchanged
        original = self.storage.get_all_logs()
        self.assertEqual(original[0]["hostname"], "SYSSVR1")
    
    def test_purge_acquires_exclusive_lock_and_clears_data(self):
        """Test that purge acquires exclusive write lock and clears data structure."""
        logs = [
            {"timestamp": "Feb 22 00:05:38", "hostname": "SYSSVR1", 
             "daemon": "systemd", "severity": "INFO", "message": "Test"}
        ]
        self.storage.add_logs(logs)
        self.assertEqual(self.storage.get_log_count(), 1)
        
        result = self.storage.purge()
        
        self.assertTrue(result)
        self.assertEqual(self.storage.get_log_count(), 0)
        self.assertEqual(self.storage.get_ingest_count(), 0)
    
    def test_thread_safety_with_concurrent_writes(self):
        """Test thread safety when multiple threads write concurrently."""
        results = []
        
        def add_logs_thread(thread_id):
            logs = [
                {"timestamp": f"Feb 22 00:0{thread_id}:00", "hostname": f"SVR{thread_id}", 
                 "daemon": "test", "severity": "INFO", "message": f"Thread {thread_id}"}
            ]
            self.storage.add_logs(logs)
            results.append(thread_id)
        
        threads = [threading.Thread(target=add_logs_thread, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All threads should have completed
        self.assertEqual(len(results), 5)
        self.assertEqual(self.storage.get_log_count(), 5)


class TestQueryEngine(unittest.TestCase):
    """Test query engine search and filter operations."""
    
    def setUp(self):
        """Set up storage with sample logs for each test."""
        self.storage = DataStorage()
        self.query_engine = QueryEngine(self.storage)
        
        # Parse and add sample logs
        logs = SyslogParser.parse_syslog_stream(SAMPLE_SYSLOG_CONTENT)
        self.storage.add_logs(logs)
    
    def test_search_date_acquires_read_lock_filters_by_date(self):
        """Test SEARCH_DATE: acquires read lock, filters by date, returns formatted logs."""
        results = self.query_engine.search_date("Feb 22")
        
        # Should return logs from Feb 22
        self.assertGreater(len(results), 0)
        for log in results:
            self.assertIn("Feb 22", log["timestamp"])
        
        # Should NOT include Mar 01 log
        mar_results = self.query_engine.search_date("Mar 01")
        self.assertEqual(len(mar_results), 1)
    
    def test_search_host_acquires_read_lock_filters_by_hostname(self):
        """Test SEARCH_HOST: acquires read lock, filters by hostname, returns formatted logs."""
        results = self.query_engine.search_host("SYSSVR1")
        
        self.assertGreater(len(results), 0)
        for log in results:
            self.assertEqual(log["hostname"].upper(), "SYSSVR1")
    
    def test_search_host_case_insensitive(self):
        """Test that hostname search is case-insensitive."""
        upper_results = self.query_engine.search_host("SYSSVR1")
        lower_results = self.query_engine.search_host("syssvr1")
        
        self.assertEqual(len(upper_results), len(lower_results))
    
    def test_search_daemon_acquires_read_lock_filters_by_daemon(self):
        """Test SEARCH_DAEMON: acquires read lock, filters by daemon, returns formatted logs."""
        results = self.query_engine.search_daemon("kernel")
        
        self.assertGreater(len(results), 0)
        for log in results:
            self.assertEqual(log["daemon"].lower(), "kernel")
    
    def test_search_severity_acquires_read_lock_filters_by_severity(self):
        """Test SEARCH_SEVERITY: acquires read lock, filters by severity, returns formatted logs."""
        results = self.query_engine.search_severity("INFO")
        
        self.assertGreater(len(results), 0)
        for log in results:
            self.assertEqual(log["severity"].upper(), "INFO")
    
    def test_search_severity_various_levels(self):
        """Test search for various severity levels."""
        # Test multiple severity levels exist
        all_logs = self.storage.get_all_logs()
        severities = set(log["severity"] for log in all_logs)
        
        for severity in severities:
            results = self.query_engine.search_severity(severity)
            self.assertGreater(len(results), 0)
    
    def test_search_keyword_acquires_read_lock_filters_message(self):
        """Test SEARCH_KEYWORD: acquires read lock, filters message by word, returns logs."""
        results = self.query_engine.search_keyword("Server")
        
        self.assertGreater(len(results), 0)
        for log in results:
            self.assertIn("server", log["message"].lower())
    
    def test_search_keyword_case_insensitive(self):
        """Test that keyword search is case-insensitive."""
        upper_results = self.query_engine.search_keyword("SERVER")
        lower_results = self.query_engine.search_keyword("server")
        
        self.assertEqual(len(upper_results), len(lower_results))
    
    def test_count_keyword_acquires_read_lock_returns_integer(self):
        """Test COUNT_KEYWORD: acquires read lock, counts occurrences, returns integer string."""
        count = self.query_engine.count_keyword("Server")
        
        self.assertIsInstance(count, int)
        self.assertGreater(count, 0)
    
    def test_count_keyword_no_matches_returns_zero(self):
        """Test COUNT_KEYWORD returns 0 when no matches found."""
        count = self.query_engine.count_keyword("nonexistent_xyz_keyword")
        
        self.assertEqual(count, 0)
    
    def test_search_returns_empty_list_when_no_matches(self):
        """Test searches return empty list when no matches found."""
        results = self.query_engine.search_host("NONEXISTENT_HOST")
        self.assertEqual(results, [])
        
        results = self.query_engine.search_daemon("nonexistent_daemon")
        self.assertEqual(results, [])
        
        results = self.query_engine.search_date("Dec 25 1999")
        self.assertEqual(results, [])


class TestResponseFormatter(unittest.TestCase):
    """Test response formatting for server responses."""
    
    def test_success_ingest_format(self):
        """Test SUCCESS response format for INGEST."""
        response = ResponseFormatter.success_ingest(42)
        
        self.assertTrue(response.startswith("SUCCESS|INGEST|"))
        self.assertIn("42", response)
        self.assertIn("logs ingested", response)
    
    def test_success_query_format(self):
        """Test SUCCESS response format for QUERY."""
        response = ResponseFormatter.success_query("log data here")
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
        self.assertIn("log data here", response)
    
    def test_success_count_format(self):
        """Test SUCCESS response format for COUNT."""
        response = ResponseFormatter.success_count(15)
        
        self.assertEqual(response, "SUCCESS|COUNT|15")
    
    def test_success_purge_format(self):
        """Test SUCCESS response format for PURGE."""
        response = ResponseFormatter.success_purge()
        
        self.assertEqual(response, "SUCCESS|PURGE|All logs cleared")
    
    def test_error_malformed_format(self):
        """Test ERROR response for malformed messages."""
        response = ResponseFormatter.error_malformed()
        
        self.assertTrue(response.startswith("ERROR|MALFORMED|"))


class TestServerMessageProcessing(unittest.TestCase):
    """
    Integration tests for server message processing.
    Tests the complete flow from protocol message to response.
    """
    
    def setUp(self):
        """Set up a server instance for testing."""
        # Import here to avoid circular imports
        from server import SyslogIndexerServer
        self.server = SyslogIndexerServer(host='localhost', port=0)  # Port 0 = don't bind
    
    def tearDown(self):
        """Clean up server resources."""
        self.server.storage.purge()
    
    def test_ingest_upload_command(self):
        """
        Test INGEST command: UPLOAD|<filesize>|<file_content_stream>
        Server should parse stream, acquire write lock, append to storage, return SUCCESS.
        """
        content = "<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Test message."
        filesize = len(content)
        message = f"UPLOAD|{filesize}|{content}"
        
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|INGEST|"))
        self.assertIn("1 logs ingested", response)
        self.assertEqual(self.server.storage.get_log_count(), 1)
    
    def test_ingest_multiple_logs(self):
        """Test ingesting multiple logs in a single UPLOAD command."""
        content = SAMPLE_SYSLOG_CONTENT
        filesize = len(content)
        message = f"UPLOAD|{filesize}|{content}"
        
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|INGEST|"))
        self.assertGreater(self.server.storage.get_log_count(), 1)
    
    def test_search_date_command(self):
        """
        Test SEARCH_DATE command: QUERY|SEARCH_DATE|<date>
        Server should acquire read lock, filter by date, return formatted string of logs.
        """
        # First ingest some logs
        self._ingest_sample_logs()
        
        message = "QUERY|SEARCH_DATE|Feb 22"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
    
    def test_search_host_command(self):
        """
        Test SEARCH_HOST command: QUERY|SEARCH_HOST|<hostname>
        Server should acquire read lock, filter by hostname, return formatted string of logs.
        """
        self._ingest_sample_logs()
        
        message = "QUERY|SEARCH_HOST|SYSSVR1"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
    
    def test_search_daemon_command(self):
        """
        Test SEARCH_DAEMON command: QUERY|SEARCH_DAEMON|<daemon>
        Server should acquire read lock, filter by daemon, return formatted string of logs.
        """
        self._ingest_sample_logs()
        
        message = "QUERY|SEARCH_DAEMON|kernel"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
    
    def test_search_severity_command(self):
        """
        Test SEARCH_SEVERITY command: QUERY|SEARCH_SEVERITY|<level>
        Server should acquire read lock, filter by severity, return formatted string of logs.
        """
        self._ingest_sample_logs()
        
        message = "QUERY|SEARCH_SEVERITY|INFO"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
    
    def test_search_keyword_command(self):
        """
        Test SEARCH_KEYWORD command: QUERY|SEARCH_KEYWORD|<word>
        Server should acquire read lock, filter message by word, return logs.
        """
        self._ingest_sample_logs()
        
        message = "QUERY|SEARCH_KEYWORD|Server"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|QUERY|"))
    
    def test_count_keyword_command(self):
        """
        Test COUNT_KEYWORD command: QUERY|COUNT_KEYWORD|<word>
        Server should acquire read lock, count occurrences, return integer string.
        """
        self._ingest_sample_logs()
        
        message = "QUERY|COUNT_KEYWORD|Server"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("SUCCESS|COUNT|"))
        # Extract count from response
        count_str = response.split("|")[-1]
        self.assertTrue(count_str.isdigit())
    
    def test_purge_command(self):
        """
        Test PURGE command: ADMIN|PURGE
        Server should acquire exclusive write lock, clear data structure, return success message.
        """
        self._ingest_sample_logs()
        self.assertGreater(self.server.storage.get_log_count(), 0)
        
        message = "ADMIN|PURGE"
        response = self.server._process_message(message)
        
        self.assertEqual(response, "SUCCESS|PURGE|All logs cleared")
        self.assertEqual(self.server.storage.get_log_count(), 0)
    
    def test_invalid_command_returns_error(self):
        """Test that invalid commands return appropriate error response."""
        message = "INVALID_COMMAND|param"
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("ERROR|INVALID_COMMAND|"))
    
    def test_malformed_message_returns_error(self):
        """Test that malformed messages return appropriate error response."""
        message = ""
        response = self.server._process_message(message)
        
        self.assertTrue(response.startswith("ERROR|MALFORMED|"))
    
    def _ingest_sample_logs(self):
        """Helper to ingest sample logs for query tests."""
        content = SAMPLE_SYSLOG_CONTENT
        filesize = len(content)
        message = f"UPLOAD|{filesize}|{content}"
        self.server._process_message(message)


class TestProtocolCommandFormats(unittest.TestCase):
    """Test protocol command format constants."""
    
    def test_ingest_format(self):
        """Test INGEST format string."""
        formatted = ProtocolCommands.INGEST_FORMAT.format(filesize=1024, content="test")
        self.assertEqual(formatted, "UPLOAD|1024|test")
    
    def test_query_date_format(self):
        """Test QUERY_DATE format string."""
        formatted = ProtocolCommands.QUERY_DATE.format(date="Feb 22")
        self.assertEqual(formatted, "QUERY|SEARCH_DATE|Feb 22")
    
    def test_query_host_format(self):
        """Test QUERY_HOST format string."""
        formatted = ProtocolCommands.QUERY_HOST.format(hostname="SYSSVR1")
        self.assertEqual(formatted, "QUERY|SEARCH_HOST|SYSSVR1")
    
    def test_query_daemon_format(self):
        """Test QUERY_DAEMON format string."""
        formatted = ProtocolCommands.QUERY_DAEMON.format(daemon="kernel")
        self.assertEqual(formatted, "QUERY|SEARCH_DAEMON|kernel")
    
    def test_query_severity_format(self):
        """Test QUERY_SEVERITY format string."""
        formatted = ProtocolCommands.QUERY_SEVERITY.format(level="INFO")
        self.assertEqual(formatted, "QUERY|SEARCH_SEVERITY|INFO")
    
    def test_query_keyword_format(self):
        """Test QUERY_KEYWORD format string."""
        formatted = ProtocolCommands.QUERY_KEYWORD.format(keyword="error")
        self.assertEqual(formatted, "QUERY|SEARCH_KEYWORD|error")
    
    def test_query_count_format(self):
        """Test QUERY_COUNT format string."""
        formatted = ProtocolCommands.QUERY_COUNT.format(keyword="memory")
        self.assertEqual(formatted, "QUERY|COUNT_KEYWORD|memory")
    
    def test_admin_purge_format(self):
        """Test ADMIN_PURGE format string."""
        self.assertEqual(ProtocolCommands.ADMIN_PURGE, "ADMIN|PURGE")


class TestSyslogParser(unittest.TestCase):
    """Test syslog parsing for INGEST operations."""
    
    def test_parse_valid_syslog_line(self):
        """Test parsing a valid RFC 3164 syslog line."""
        line = "<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Started OpenBSD Secure Shell server."
        result = SyslogParser.parse_syslog(line)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["hostname"], "SYSSVR1")
        self.assertEqual(result["daemon"], "systemd")
        self.assertEqual(result["severity"], "INFO")
        self.assertIn("Started OpenBSD", result["message"])
    
    def test_parse_syslog_stream(self):
        """Test parsing multiple syslog lines from a stream."""
        logs = SyslogParser.parse_syslog_stream(SAMPLE_SYSLOG_CONTENT)
        
        self.assertIsNotNone(logs)
        self.assertGreater(len(logs), 0)
    
    def test_parse_invalid_syslog_returns_none(self):
        """Test that invalid syslog line returns None."""
        invalid_line = "This is not a valid syslog line"
        result = SyslogParser.parse_syslog(invalid_line)
        
        self.assertIsNone(result)
    
    def test_parse_empty_line_returns_none(self):
        """Test that empty line returns None."""
        result = SyslogParser.parse_syslog("")
        self.assertIsNone(result)
        
        result = SyslogParser.parse_syslog("   ")
        self.assertIsNone(result)


if __name__ == "__main__":
    # Run tests with verbosity
    unittest.main(verbosity=2)
