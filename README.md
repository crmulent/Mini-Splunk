# Mini-Splunk: Concurrent Syslog Analytics Server

A lightweight, centralized log management server that ingests, parses, and indexes standard syslog files from multiple concurrent CLI clients.

## Project Overview

**Course:** NSAPDEV (Server Application Development)  
**Project Title:** Concurrent Syslog Analytics Server ("Mini-Splunk")  
**Version:** 1.0  
**Python Version:** 3.7+

### Purpose

Mini-Splunk is a multithreaded syslog analytics server designed to:
- Ingest syslog files from multiple concurrent CLI clients
- Parse RFC 3164 syslog format
- Index and store logs in memory with thread-safe access
- Execute concurrent queries based on date, hostname, daemon, severity, and keywords
- Provide search and statistical analysis capabilities

### Core Capabilities

✓ **RFC 3164 Syslog Parsing** - Converts raw syslog lines into structured data  
✓ **Concurrent Client Support** - Thread-per-connection model handles multiple clients  
✓ **Thread-Safe Data Storage** - RLock prevents race conditions during concurrent access  
✓ **Advanced Querying** - Search by date, host, daemon, severity, or keyword  
✓ **Statistical Analysis** - Generate statistics on indexed logs  
✓ **Administrative Functions** - Purge logs, view statistics  

## Architecture

### High-Level Architecture

**Architectural Style:** Client-Server with multithreaded backend

```
┌─────────────────────────────────────────────────────────────┐
│                    Network Layer (TCP)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐        ┌──────────────────────────┐   │
│  │ CLI Forwarder #1 │        │  Indexer Server          │   │
│  │   (Client)       │───────▶│  (Main Listener Thread)  │   │
│  └──────────────────┘        │                          │   │
│                              │  ┌──────────────────────┐│   │
│  ┌──────────────────┐        │  │ Worker Thread Pool   ││   │
│  │ CLI Forwarder #2 │───────▶│  │ (Thread-per-Conn)    ││   │
│  │   (Client)       │        │  │                      ││   │
│  └──────────────────┘        │  ├──────────────────────┤│   │
│                              │  │ Critical Section:    ││   │
│                              │  │ Shared Data Storage  ││   │
│  ┌──────────────────┐        │  │ Protected by RLock   ││   │
│  │ CLI Forwarder #N │───────▶│  │                      ││   │
│  │   (Client)       │        │  └──────────────────────┘│   │
│  └──────────────────┘        │                          │   │
│                              └──────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### System Components

#### 1. **The Forwarder (CLI Client)**
- **Responsible for:**
  - Parsing user commands
  - Reading local syslog files
  - Establishing TCP connections
  - Rendering server responses
- **File:** `client.py`
- **Modes:** Single-command or interactive shell

#### 2. **The Indexer (Server)**
- **Responsible for:**
  - Listening on a defined port (default: 5514)
  - Dispatching worker threads for each connection
  - Safely modifying shared memory
  - Executing search functions
- **File:** `server.py`
- **Threading Model:** Thread-per-Connection

#### 3. **Supporting Modules**
- **`syslog_parser.py`** - RFC 3164 parsing with regex
- **`data_storage.py`** - Thread-safe in-memory storage with RLock
- **`query_engine.py`** - Search and filtering functions
- **`protocol.py`** - Client-server protocol definitions

## Concurrency and Threading Model

### Connection Handling (Thread-per-Connection)

The server uses a **Thread-per-Connection model**:

1. **Main Listener Thread** continuously accepts TCP connections
2. Upon accepting a connection:
   - Create a new worker thread
   - Pass the socket object to the worker
   - Main thread immediately returns to accepting the next connection
3. **Worker Thread** handles all communication with that specific client

**Benefits:**
- Multiple clients can be served simultaneously
- Main listener never blocks
- Simple synchronization model for thread pool

```python
# Pseudocode
while server_running:
    client_socket, address = server_socket.accept()
    worker_thread = spawn_thread(handle_client, client_socket)
    # Main thread immediately returns to accept()
```

### Isolation & Synchronization (Critical Section)

**Problem:** Multiple clients might INGEST files or PURGE logs simultaneously, causing race conditions on the shared log storage.

**Solution:** Use `threading.RLock` (Reentrant Lock)

```python
# Data Storage with RLock
class DataStorage:
    def __init__(self):
        self._logs = []  # Shared critical section
        self._lock = threading.RLock()  # Mutual exclusion
    
    def add_logs(self, logs):
        with self._lock:  # Acquire lock
            self._logs.extend(logs)  # Safe modification
            # Lock automatically released on exit
    
    def get_all_logs(self):
        with self._lock:
            return [log.copy() for log in self._logs]
```

**RLock Features:**
- Allows the same thread to acquire the lock multiple times
- Prevents race conditions
- Ensures FIFO ordering for waiting threads
- Automatically released when exiting `with` block

## Domain and Functional Decomposition

### Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Network Module                            │
│            (TCP socket operations)                          │
├─────────────────────────────────────────────────────────────┤
│  Handles: socket.bind(), socket.listen(), socket.accept()   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  Parsing Module                             │
│       (RFC 3164 Regex parsing)                              │
├─────────────────────────────────────────────────────────────┤
│  syslog_parser.py: Converts raw strings → Dict objects      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Data Storage Module                            │
│          (Shared memory + Locking)                          │
├─────────────────────────────────────────────────────────────┤
│  data_storage.py: Global list + RLock protection            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│               Query Engine Module                           │
│            (Search & Filter functions)                      │
├─────────────────────────────────────────────────────────────┤
│  query_engine.py: SEARCH_DATE, SEARCH_HOST, COUNT, etc.     │
└─────────────────────────────────────────────────────────────┘
```

## Shared Data State Layout

### Data Structure

Global Python List of Dictionaries (in-memory database):

```python
logs = [
    {
        "timestamp": "Feb 22 00:05:38",
        "hostname": "SYSSVR1",
        "daemon": "systemd",
        "severity": "INFO",
        "message": "Started OpenBSD Secure Shell server..."
    },
    {
        "timestamp": "Feb 22 00:06:00",
        "hostname": "SYSSVR2",
        "daemon": "kernel",
        "severity": "WARNING",
        "message": "Out of memory: Kill process 1234..."
    },
    # ... more log entries
]
```

### Schema

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | str | RFC 3164 timestamp | "Feb 22 00:05:38" |
| `hostname` | str | Source hostname | "SYSSVR1" |
| `daemon` | str | Daemon/program name | "systemd", "kernel", "httpd" |
| `severity` | str | RFC 3164 severity level | "INFO", "WARNING", "ERR", etc. |
| `message` | str | Log message content | "Service started..." |

## Client-Server Communication Protocol

### Protocol Overview

All messages use pipe-delimited format: `COMMAND|PARAM1|PARAM2|...`

### Client Commands & Responses

| Command | Format | Server Action | Response |
|---------|--------|----------------|----------|
| **INGEST** | `UPLOAD\|<filesize>\|<content>` | Parse stream, acquire write lock, append to storage | `SUCCESS\|INGEST\|N logs ingested` |
| **SEARCH_DATE** | `QUERY\|SEARCH_DATE\|<date>` | Acquire read lock, filter by date | `SUCCESS\|QUERY\|<formatted_logs>` |
| **SEARCH_HOST** | `QUERY\|SEARCH_HOST\|<hostname>` | Acquire read lock, filter by hostname | `SUCCESS\|QUERY\|<formatted_logs>` |
| **SEARCH_DAEMON** | `QUERY\|SEARCH_DAEMON\|<daemon>` | Acquire read lock, filter by daemon | `SUCCESS\|QUERY\|<formatted_logs>` |
| **SEARCH_SEVERITY** | `QUERY\|SEARCH_SEVERITY\|<level>` | Acquire read lock, filter by severity | `SUCCESS\|QUERY\|<formatted_logs>` |
| **SEARCH_KEYWORD** | `QUERY\|SEARCH_KEYWORD\|<word>` | Acquire read lock, filter message | `SUCCESS\|QUERY\|<formatted_logs>` |
| **COUNT_KEYWORD** | `QUERY\|COUNT_KEYWORD\|<word>` | Acquire read lock, count occurrences | `SUCCESS\|COUNT\|<number>` |
| **PURGE** | `ADMIN\|PURGE` | Acquire exclusive write lock, clear data | `SUCCESS\|PURGE\|All logs cleared` |
| **STATS** | `ADMIN\|STATS` | Get statistics | `STATS\|<stats_string>` |
| **HELP** | `HELP` | Display help | `INFO\|<help_text>` |

### Error Responses

| Error | Format |
|-------|--------|
| Invalid command | `ERROR\|INVALID_COMMAND\|Unknown command: X` |
| Malformed message | `ERROR\|MALFORMED\|Message format is incorrect` |
| Parse error | `ERROR\|PARSE\|Failed to parse log entry` |
| I/O error | `ERROR\|IO\|File I/O error: details` |
| Internal error | `ERROR\|INTERNAL\|Server error: details` |

## Installation & Setup

### Requirements

- Python 3.7 or higher
- Standard library only (socket, threading, re, datetime)
- No external dependencies

### Project Structure

```
Mini-Splunk/
├── server.py              # Indexer server application
├── client.py              # Forwarder CLI client
├── syslog_parser.py       # RFC 3164 syslog parser
├── data_storage.py        # Thread-safe data storage
├── query_engine.py        # Query and search engine
├── protocol.py            # Protocol definitions
├── README.md              # This file
└── sample_logs.txt        # Sample syslog file (optional)
```

### Quick Start

#### Terminal 1: Start the Server

```bash
python server.py --host localhost --port 5514
```

Output:
```
[MainListener] INFO Server started on localhost:5514
[MainListener] INFO Listening on localhost:5514
```

#### Terminal 2: Start the Client

##### Interactive Mode:
```bash
python client.py
```

Output:
```
✓ Connected to server at localhost:5514

============================================================
Mini-Splunk Forwarder Client - Interactive Mode
============================================================
Type 'help' for available commands, 'quit' to exit

splunk>
```

##### Single Command Mode:
```bash
python client.py ingest /var/log/syslog
python client.py search-host SYSSVR1
python client.py count-keyword "error"
```

## Usage Examples

### Example 1: Ingest a Syslog File

**Client Side:**
```bash
splunk> ingest /var/log/syslog
→ Uploading 524288 bytes from /var/log/syslog...
✓ 1043 logs ingested
```

**Server Side (logs):**
```
[Worker-127.0.0.1:54321] INFO New client connection from ('127.0.0.1', 54321)
[Worker-127.0.0.1:54321] INFO Ingested 1043 logs
```

### Example 2: Search Logs by Date

```bash
splunk> search-date "Feb 22"
→ Searching logs for date: Feb 22...
✓ 1. [Feb 22 00:05:38] Host: SYSSVR1 | Daemon: systemd | Severity: INFO | Msg: Started OpenBSD Secure Shell server.
2. [Feb 22 00:06:15] Host: SYSSVR2 | Daemon: kernel | Severity: WARNING | Msg: Out of memory: Kill process 1234
3. [Feb 22 00:07:30] Host: SYSSVR1 | Daemon: httpd | Severity: INFO | Msg: Request processed
```

### Example 3: Search by Hostname

```bash
splunk> search-host SYSSVR1
→ Searching logs for host: SYSSVR1...
✓ 1. [Feb 22 00:05:38] Host: SYSSVR1 | Daemon: systemd | Severity: INFO | Msg: Started OpenBSD Secure Shell server.
2. [Feb 22 00:07:30] Host: SYSSVR1 | Daemon: httpd | Severity: INFO | Msg: Request processed
```

### Example 4: Search by Keyword

```bash
splunk> search-keyword "error"
→ Searching logs for keyword: 'error'...
✓ 1. [Feb 22 01:45:22] Host: SYSSVR3 | Daemon: mysql | Severity: ERR | Msg: Connection error: timeout
2. [Feb 22 02:10:15] Host: SYSSVR1 | Daemon: sshd | Severity: WARNING | Msg: Invalid user attempt, logging error
```

### Example 5: Count Keyword Occurrences

```bash
splunk> count-keyword "failed"
→ Counting occurrences of 'failed'...
✓ 47
```

### Example 6: Get Statistics

```bash
splunk> stats
→ Requesting server statistics...
✓ total_logs: 1043 | unique_hosts: 3 | unique_daemons: 12 | unique_severities: 6
```

### Example 7: Purge All Logs

```bash
splunk> purge
Are you sure? (yes/no): yes
→ Purging all logs from server...
✓ All logs cleared
```

### Example 8: Get Help

```bash
splunk> help
→ SUPPORTED COMMANDS:
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
```

## RFC 3164 Syslog Format

### Standard Format

```
<PRI>MMM DD HH:MM:SS HOSTNAME TAG[PID]: MESSAGE
```

### Components

- **`<PRI>`** (Priority): Facility and Severity encoded as 8-bit integer (optional)
  - Facility: bits 3-7 (multiplied by 8)
  - Severity: bits 0-2
  - Example: `<134>` = facility 16 (local0) * 8 + severity 6 (info)

- **`MMM`** (Month): 3-letter month abbreviation (Jan, Feb, Mar, etc.)

- **`DD`** (Day): 2-digit day of month

- **`HH:MM:SS`** (Time): 24-hour time

- **`HOSTNAME`** (Host): Source hostname

- **`TAG[PID]`** (Daemon): Process name, optionally with PID in brackets

- **`MESSAGE`** (Message): Log message content

### Severity Levels

| Code | Level | Name |
|------|-------|------|
| 0 | Emergency | EMERG |
| 1 | Alert | ALERT |
| 2 | Critical | CRIT |
| 3 | Error | ERR |
| 4 | Warning | WARNING |
| 5 | Notice | NOTICE |
| 6 | Informational | INFO |
| 7 | Debug | DEBUG |

### Example Syslog Entries

```
<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Started OpenBSD Secure Shell server.
Feb 22 00:06:15 SYSSVR2 kernel: Out of memory: Kill process 1234 (java) score 156 or sacrifice child
<85>Feb 22 00:07:30 SYSSVR1 httpd[8234]: POST /api/users HTTP/1.1 200 1234
Feb 22 01:45:22 SYSSVR3 mysql[456]: [ERROR] InnoDB: Connection error: timeout
```

## Advanced Features

### Thread Safety & Concurrency

The system is designed to handle:
- **Concurrent ingests** from multiple clients
- **Concurrent queries** while ingests are happening
- **Lock-free reads** when no writes are in progress
- **Exclusive writes** during PURGE operations

**Lock Hierarchy:**
1. Read operations acquire RLock (shared access)
2. Write operations (INGEST, PURGE) acquire RLock (exclusive)
3. Administrative operations can happen concurrently with queries

### Performance Considerations

- **In-memory storage** provides fast access (O(n) for filtering)
- **Thread pool** handles connection load
- **Socket timeout** prevents hung connections
- **Lazy copy** of logs prevents expensive full clones

### Scalability

For larger datasets, consider:
- Moving to a proper database (SQLite, PostgreSQL)
- Implementing indexing structures (B-trees, hash tables)
- Using connection pooling
- Implementing log rotation/archival

## Testing

### Unit Test Examples

```python
# Test syslog parsing
from syslog_parser import SyslogParser

log_line = "<134>Feb 22 00:05:38 SYSSVR1 systemd: Service started"
parsed = SyslogParser.parse_syslog(log_line)
assert parsed['hostname'] == 'SYSSVR1'
assert parsed['severity'] == 'INFO'
```

```python
# Test data storage
from data_storage import DataStorage

storage = DataStorage()
logs = [{"hostname": "HOST1", "message": "test"}]
storage.add_logs(logs)
assert storage.get_log_count() == 1
```

```python
# Test query engine
from query_engine import QueryEngine
from data_storage import DataStorage

storage = DataStorage()
engine = QueryEngine(storage)
# Add test data and verify searches...
```

## Troubleshooting

### Server won't start

```
Error: Address already in use
Solution: Change port with --port option or kill process on port 5514
```

### Client can't connect

```
✗ Failed to connect: Connection refused
Solution: Ensure server is running on correct host:port
```

### No results from queries

```
Possible reasons:
1. No logs ingested yet
2. Search parameters don't match log data
3. Use exact case-insensitive matching for hostname, daemon
```

## References

- RFC 3164: The BSD syslog Protocol
  - https://tools.ietf.org/html/rfc3164

- Python threading documentation
  - https://docs.python.org/3/library/threading.html

- Socket programming in Python
  - https://docs.python.org/3/library/socket.html

- Regular Expressions (re) module
  - https://docs.python.org/3/library/re.html

## Architecture Diagram

```
CLIENT #1          CLIENT #2          CLIENT #N
  │                  │                  │
  │ TCP Connect      │ TCP Connect      │ TCP Connect
  ↓                  ↓                  ↓
┌─────────────────────────────────────────────┐
│     SERVER LISTENING THREAD (Port 5514)     │
│                                             │
│ while running:                              │
│   connection = accept()                     │
│   spawn_worker_thread(connection)           │
└─────────────────────────────────────────────┘
  │                  │                  │
  │ Hand off         │ Hand off         │ Hand off
  ↓                  ↓                  ↓
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│Worker Thread1│ │Worker Thread2│ │Worker ThreadN│
└──────────────┘ └──────────────┘ └──────────────┘
  │                  │                  │
  │ All read/write to↓                  │
  ├─────────────┬────┴──────────────────┤
  │             │                       │
  ↓             ↓                       ↓
┌──────────────────────────────────────────────┐
│    CRITICAL SECTION (Protected by RLock)     │
│                                              │
│    [Log #1, Log #2, Log #3, ... Log #N]      │
│                                              │
│    Thread mutex:  threading.RLock()          │
│    Status: Thread-safe                       │
└──────────────────────────────────────────────┘
```

## License

This project is part of the NSAPDEV course assignment.

## Contact

For questions or issues, contact your course instructor.

---

**Last Updated:** March 9, 2026  
**Version:** 1.0
