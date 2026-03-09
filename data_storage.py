"""
Data Storage Module
Manages shared memory state with thread-safe locking mechanisms.
Implements Critical Section protection using RLock (Reentrant Lock).
"""

import threading
from typing import List, Dict, Optional
from collections import defaultdict


class DataStorage:
    """
    Thread-safe data storage for parsed syslog entries.
    
    Uses RLock (Reentrant Lock) to prevent race conditions when multiple
    clients ingest files or perform queries simultaneously.
    """
    
    def __init__(self):
        """Initialize the data storage with a shared list and locking mechanism."""
        # Critical section: protected list of parsed logs
        self._logs: List[Dict] = []
        
        # RLock allows the same thread to acquire the lock multiple times
        # Semaphore would also work, but RLock is more suitable for re-entrancy
        self._lock = threading.RLock()
        
        # Metadata
        self._host_count = 0
        self._ingest_count = 0
    
    def add_logs(self, logs: List[Dict]) -> bool:
        """
        Add logs to storage (thread-safe).
        Acquires write lock before modifying shared data.
        
        Args:
            logs: List of parsed log dictionaries
            
        Returns:
            True if successful
        """
        if not logs:
            return True
        
        with self._lock:
            self._logs.extend(logs)
            self._ingest_count += 1
            
            # Update host count
            hosts = set(log.get('hostname', '') for log in logs)
            self._host_count = len(set(log.get('hostname', '') for log in self._logs))
        
        return True
    
    def get_all_logs(self) -> List[Dict]:
        """
        Retrieve all logs (thread-safe).
        Acquires read lock.
        
        Returns:
            List of all log dictionaries
        """
        with self._lock:
            # Return a copy to prevent external modifications
            return [log.copy() for log in self._logs]
    
    def purge(self) -> bool:
        """
        Clear all logs (thread-safe).
        Acquires exclusive write lock.
        
        Returns:
            True if successful
        """
        with self._lock:
            self._logs.clear()
            self._ingest_count = 0
            self._host_count = 0
        
        return True
    
    def get_log_count(self) -> int:
        """
        Get total number of logs (thread-safe).
        
        Returns:
            Number of logs in storage
        """
        with self._lock:
            return len(self._logs)
    
    def get_ingest_count(self) -> int:
        """
        Get number of ingest operations (thread-safe).
        
        Returns:
            Number of ingest operations performed
        """
        with self._lock:
            return self._ingest_count
    
    def get_host_count(self) -> int:
        """
        Get number of unique hosts (thread-safe).
        
        Returns:
            Number of unique hostnames
        """
        with self._lock:
            hosts = set(log.get('hostname', '') for log in self._logs)
            return len(hosts)
    
    # Acquire lock for filtering operations
    def acquire_read_lock(self):
        """Acquire read lock for filtering operations."""
        self._lock.acquire()
    
    def release_read_lock(self):
        """Release read lock after filtering operations."""
        self._lock.release()
    
    def _filter_by_field(self, field: str, value: str, logs: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Internal helper to filter logs by a specific field.
        
        Args:
            field: Field name to filter by
            value: Value to match
            logs: Optional list of logs to filter (defaults to all logs)
            
        Returns:
            Filtered list of logs
        """
        if logs is None:
            logs = self.get_all_logs()
        
        return [log for log in logs if log.get(field, '').lower() == value.lower()]
    
    def _filter_by_message(self, keyword: str, logs: Optional[List[Dict]] = None) -> List[Dict]:
        """
        Internal helper to filter logs by keyword in message.
        
        Args:
            keyword: Keyword to search for
            logs: Optional list of logs to filter (defaults to all logs)
            
        Returns:
            Filtered list of logs
        """
        if logs is None:
            logs = self.get_all_logs()
        
        keyword_lower = keyword.lower()
        return [log for log in logs if keyword_lower in log.get('message', '').lower()]
    
    def __repr__(self):
        return f"DataStorage(logs={self.get_log_count()}, hosts={self.get_host_count()}, ingests={self.get_ingest_count()})"


# Global singleton storage instance
_global_storage: Optional[DataStorage] = None
_storage_lock = threading.Lock()


def get_global_storage() -> DataStorage:
    """
    Get or create the global singleton storage instance.
    Thread-safe initialization.
    
    Returns:
        Global DataStorage instance
    """
    global _global_storage
    
    if _global_storage is None:
        with _storage_lock:
            if _global_storage is None:
                _global_storage = DataStorage()
    
    return _global_storage


# For testing
if __name__ == "__main__":
    storage = DataStorage()
    
    # Test add logs
    test_logs = [
        {"timestamp": "Feb 22 00:05:38", "hostname": "HOST1", "daemon": "systemd", "severity": "INFO", "message": "Service started"},
        {"timestamp": "Feb 22 00:06:00", "hostname": "HOST2", "daemon": "kernel", "severity": "WARNING", "message": "Low memory"},
    ]
    
    storage.add_logs(test_logs)
    print(f"Storage: {storage}")
    print(f"All logs: {storage.get_all_logs()}")
    
    # Test filtering
    filtered = storage._filter_by_field("hostname", "HOST1")
    print(f"Filtered by HOST1: {filtered}")
