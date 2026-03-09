# Mini-Splunk Architecture Design Document

## Executive Summary

Mini-Splunk is a concurrent syslog analytics server implementing a **Client-Server architecture** with a **Thread-per-Connection model**. The system is designed to safely handle multiple concurrent clients ingesting and querying syslog data without race conditions through careful synchronization using reentrant locks.

---

## 1. System Overview

### Purpose

A lightweight, centralized log management server that ingests, parses, and indexes standard syslog files from multiple concurrent CLI clients. It provides real-time search and analytical capabilities over indexed logs.

### Core Capabilities

- **RFC 3164 Syslog Ingestion**: Parse and index syslog files in standard format
- **Concurrent Client Support**: Handle multiple simultaneous client connections
- **Thread-Safe Operations**: Prevent race conditions through proper synchronization
- **Advanced Querying**: Search by date, hostname, daemon, severity, and keywords
- **Statistical Analysis**: Generate insights about log data
- **Administrative Control**: Purge logs, view metrics

---

## 2. High-Level Architecture Model

### Architectural Style

**Client-Server with Multithreaded Backend**

The system consists of two primary components:

1. **Indexer Server (Multithreaded)**: Central log aggregation and query engine
2. **Forwarder Client(s)**: CLI interface for log ingestion and queries

### System Components Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                        TCP NETWORK LAYER                         │
└──────────────────────────────────────────────────────────────────┘
              ↑                    ↑                   ↑
      Port 5514 (Conn1)   Port 5514 (Conn2)  Port 5514 (ConnN)
              │                    │                   │
       ┌──────┴──────┐      ┌──────┴──────┐      ┌───┴─────────┐
       │   CLIENT #1 │      │   CLIENT #2 │      │  CLIENT #N  │
       │ (Forwarder) │      │ (Forwarder) │      │ (Forwarder) │
       └─────────────┘      └─────────────┘      └─────────────┘

                           ↓ ↓ ↓ (connections)

       ┌──────────────────────────────────────────────────────────┐
       │           INDEXER SERVER (server.py)                    │
       │                                                          │
       │  ┌────────────────────────────────────────────────────┐ │
       │  │  MAIN LISTENER THREAD                              │ │
       │  │  while server_running:                             │ │
       │  │    socket.accept()  → spawn_worker_thread()        │ │
       │  └────────────────────────────────────────────────────┘ │
       │                          │                               │
       │         ┌────────────────┼────────────────┐              │
       │         ↓                ↓                ↓              │
       │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
       │  │Worker       │  │Worker        │  │Worker        │   │
       │  │Thread #1    │  │Thread #2     │  │Thread #N     │   │
       │  └──────────────┘  └──────────────┘  └──────────────┘   │
       │         │                ↓                ↑              │
       │         └────────────────┼────────────────┘              │
       │                          ↓                               │
       │  ┌──────────────────────────────────────────────────────┐│
       │  │     CRITICAL SECTION (data_storage.py)              ││
       │  │                                                      ││
       │  │  Shared Data: [ Log#1, Log#2, ... Log#N ]          ││
       │  │  Protection: threading.RLock()                      ││
       │  │  Status: Thread-Safe ✓                              ││
       │  └──────────────────────────────────────────────────────┘│
       └──────────────────────────────────────────────────────────┘
```

### The Forwarder (CLI Client)

**Responsible for:**
- Parsing user commands (interactive or command-line)
- Reading local syslog files from disk
- Establishing TCP connections to server
- Serializing commands into protocol format
- Rendering/displaying server responses

**Implementation:** `client.py`

**Usage Modes:**
- Interactive shell: `python client.py`
- Single command: `python client.py ingest /var/log/syslog`

### The Indexer (Server)

**Responsible for:**
- Listening on a defined port (default: 5514)
- Accepting TCP connections from clients
- Dispatching worker threads for each connection
- Safely modifying shared memory using locks
- Executing search and indexing functions
- Formatting and sending responses

**Implementation:** `server.py`

**Key Properties:**
- **Thread-per-Connection**: One thread per active client
- **Stateful**: Maintains in-memory index of logs
- **Concurrent**: Multiple queries can execute simultaneously
- **Fault-tolerant**: Worker thread failures don't affect other clients

---

## 3. Concurrency and Threading Model

### Connection Handling: Thread-per-Connection Model

The server uses a **Thread-per-Connection** approach, which is ideal for I/O-bound operations like network communication.

#### How It Works:

```
1. Main Listener Thread Startup
   ├─ Create server socket
   ├─ Bind to port 5514
   ├─ Listen with backlog=10
   └─ Enter accept loop

2. Accept Loop (Main Thread)
   while server.running:
       │
       ├─ socket.accept()  ← Blocks until new connection
       │
       ├─ Create new Worker Thread
       │
       ├─ Pass socket to worker
       │
       └─ Return to accept()  ← Non-blocking!

3. Worker Thread (Spawned)
   for each client:
       ├─ Read message from socket
       ├─ Parse command
       ├─ Acquire lock on shared data
       ├─ Process command
       ├─ Release lock
       ├─ Send response
       └─ Repeat until client disconnects
```

#### Benefits:

| Benefit | Explanation |
|---------|-------------|
| **Simplicity** | Each thread handles one client sequentially |
| **Scalability** | Can handle 1000s of clients (OS limit) |
| **Non-blocking** | Listener never blocked by slow clients |
| **Easy Debugging** | Stack traces per client are clear |

#### Python Implementation:

```python
def _run_server(self):
    server_socket = socket.socket()
    server_socket.bind(('localhost', 5514))
    server_socket.listen(10)
    
    while self.running:
        # Blocks here until connection arrives
        client_socket, address = server_socket.accept()
        
        # Spawn worker thread and immediately return
        worker = threading.Thread(
            target=self._handle_client,
            args=(client_socket, address),
            daemon=True
        )
        worker.start()  # Non-blocking!
```

### Isolation & Synchronization: Critical Section

#### The Problem: Race Conditions

When multiple workers access shared data simultaneously without synchronization:

```python
# UNSAFE - Race condition!
def add_logs(logs):
    global shared_log_list
    
    # Thread A reads: len=100
    # Thread B reads: len=100 (same time)
    # Thread A writes: len=150 (lost Thread B's update)
    # Thread B writes: len=105 (overwrites Thread A's update)
    # Result: Lost data!
    
    temp = shared_log_list  # Read
    temp.extend(logs)        # Modify
    shared_log_list = temp   # Write (RACE!)
```

#### The Solution: Threading.RLock

**RLock (Reentrant Lock)** prevents multiple threads from accessing the critical section simultaneously:

```python
import threading

class DataStorage:
    def __init__(self):
        self._logs = []  # Critical section
        self._lock = threading.RLock()  # Guard
    
    def add_logs(self, logs):
        with self._lock:  # Acquire lock
            # Only one thread at a time!
            for wait_log in self._logs + logs:
                if wait_log not in self._logs:
                    self._logs.append(log)
        # Lock automatically released
    
    def get_all_logs(self):
        with self._lock:  # Also protect reads
            return [log.copy() for log in self._logs]
```

#### Why RLock?

```
ISSUE: Deep call stacks
──────────────────────
Thread A:                 Thread A State:
add_logs()          →     Lock acquired
  ├─ with self._lock:
  │  └─ _validate()  →    Needs lock again!
  │     └─ with self._lock:  ← DEADLOCK with Lock!
  │                         ← OK with RLock!

RLock allows same thread to acquire multiple times:
- Thread A: acquire() → acquire() → release() → release() ✓

Regular Lock doesn't:
- Thread A: acquire() → acquire() → DEADLOCK! ✗
```

#### Lock Semantics:

```python
# Multiple readers (implicit)
# Queries happen concurrently
thread_1: query_engine.search_host()
thread_2: query_engine.search_keyword()  # No wait!

# Exclusive writer
# Ingest blocks readers
thread_3: storage.add_logs()  # Gets lock
thread_1: (blocked on read)
thread_2: (blocked on read)

# PURGE = exclusive writer
# Most restrictive operation
thread_4: storage.purge()     # Gets lock
# Everyone blocked
```

#### Race Condition Examples Prevented:

**Example 1: Lost Writes**
```
Without lock:
A: read count (=10)      B: read count (=10)
A: compute (10+5=15)     B: compute (10+3=13)
A: write count (=15)     B: write count (=13)
Result: Lost one update! ✗

With RLock:
A: acquire(), read, compute, write, release()
B: waits...
B: acquire(), read, compute, write, release()
Result: Both updates applied ✓
```

**Example 2: Dirty Reads**
```
Without lock:
A: add([log1, log2, log3])
B: get_all() during add
Result: B gets [log1] - incomplete! ✗

With RLock:
A: acquire(), add(logs), release()
B: acquire() - waits for A, release()
Result: B gets [log1, log2, log3] - complete ✓
```

---

## 4. Domain and Functional Decomposition

### Module Structure

The system is decomposed into five focused modules, each handling one domain:

```
┌─────────────────────────────────────────┐
│        NETWORK MODULE                   │
│    (server.py, client.py)              │
├─────────────────────────────────────────┤
│  Responsibilities:                      │
│  • socket.bind() / listen() / accept()  │
│  • TCP connection management            │
│  • Worker thread dispatching            │
│  • Message I/O over sockets             │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      PARSING MODULE                     │
│    (syslog_parser.py)                  │
├─────────────────────────────────────────┤
│  Responsibilities:                      │
│  • RFC 3164 regex pattern matching      │
│  • Extract timestamp, host, daemon, etc │
│  • Convert strings → structured dicts   │
│  • File I/O for syslog ingestion        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│    DATA STORAGE MODULE                  │
│    (data_storage.py)                   │
├─────────────────────────────────────────┤
│  Responsibilities:                      │
│  • Maintain global log list             │
│  • RLock for mutual exclusion           │
│  • Thread-safe add/read/purge           │
│  • Metadata (counts, hosts, etc)        │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│      QUERY ENGINE MODULE                │
│    (query_engine.py)                   │
├─────────────────────────────────────────┤
│  Responsibilities:                      │
│  • SEARCH_DATE / SEARCH_HOST            │
│  • SEARCH_DAEMON / SEARCH_SEVERITY      │
│  • SEARCH_KEYWORD / COUNT_KEYWORD       │
│  • Format results for display           │
│  • Compute statistics                   │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│     PROTOCOL MODULE                     │
│    (protocol.py)                       │
├─────────────────────────────────────────┤
│  Responsibilities:                      │
│  • Message format definitions           │
│  • Parse command strings                │
│  • Format response strings              │
│  • Protocol constants                   │
└─────────────────────────────────────────┘
```

### Module Details

#### 1. Network Module (server.py, client.py)

**Server Side:**
```python
class SyslogIndexerServer:
    def _run_server():
        # Main listener loop
        socket.bind(('localhost', 5514))
        socket.listen(10)
        while running:
            conn, addr = socket.accept()
            spawn_worker(handle_client, conn)

    def _handle_client(socket, address):
        # Worker thread - one per client
        while connected:
            msg = socket.recv(65536)
            response = process_message(msg)
            socket.send(response)
```

**Client Side:**
```python
class SyslogForwarderClient:
    def connect():
        socket.connect(('localhost', 5514))
    
    def ingest_file(path):
        content = read_file(path)
        command = f"UPLOAD|{len(content)}|{content}"
        socket.send(command)
        response = socket.recv(65536)
        display(response)
```

#### 2. Parsing Module (syslog_parser.py)

**RFC 3164 Format:**
```
<PRI>MMM DD HH:MM:SS HOSTNAME DAEMON[PID]: MESSAGE
<134>Feb 22 00:05:38 SYSSVR1 systemd[1]: Service started
```

**Regex Pattern:**
```python
PATTERN = r'^(?:<(\d+)>)?'  # Optional priority
           r'(\w+ \d+ \d{2}:\d{2}:\d{2})\s+'  # Timestamp
           r'(\S+)\s+'  # Hostname
           r'(\w+)(?:\[(\d+)\])?:'  # Daemon + PID
           r'(.*)$'  # Message
```

**Output:**
```python
{
    "timestamp": "Feb 22 00:05:38",
    "hostname": "SYSSVR1",
    "daemon": "systemd",
    "severity": "INFO",
    "message": "Service started"
}
```

#### 3. Data Storage Module (data_storage.py)

**Thread-Safe Operations:**

```python
class DataStorage:
    def __init__(self):
        self._logs = []
        self._lock = threading.RLock()
    
    # Write operation (exclusive)
    def add_logs(self, logs):
        with self._lock:  # EXCLUSIVE
            self._logs.extend(logs)
    
    # Read operation (concurrent)
    def get_all_logs(self):
        with self._lock:  # Safe read
            return [log.copy() for log in self._logs]
    
    # Nuclear option
    def purge(self):
        with self._lock:  # EXCLUSIVE
            self._logs.clear()
```

#### 4. Query Engine Module (query_engine.py)

```python
class QueryEngine:
    def search_host(self, hostname):
        logs = storage.get_all_logs()
        return [log for log in logs 
                if log['hostname'].lower() == hostname.lower()]
    
    def search_keyword(self, keyword):
        logs = storage.get_all_logs()
        return [log for log in logs
                if keyword.lower() in log['message'].lower()]
    
    def count_keyword(self, keyword):
        return len(self.search_keyword(keyword))
    
    def get_statistics(self):
        logs = storage.get_all_logs()
        return {
            'total': len(logs),
            'hosts': len(set(l['hostname'] for l in logs)),
            # ...
        }
```

#### 5. Protocol Module (protocol.py)

**Message Formats:**

| Operation | Format | Response |
|-----------|--------|----------|
| Ingest | `UPLOAD\|size\|content` | `SUCCESS\|INGEST\|42 logs` |
| Search | `QUERY\|SEARCH_HOST\|SYSSVR1` | `SUCCESS\|QUERY\|<logs>` |
| Count | `QUERY\|COUNT_KEYWORD\|error` | `SUCCESS\|COUNT\|7` |
| Purge | `ADMIN\|PURGE` | `SUCCESS\|PURGE\|Cleared` |

---

## 5. Shared Data State Layout

### In-Memory Database

**Structure:** Global Python List of Dictionaries

```python
# Global state (protected by RLock in DataStorage)
_logs: List[Dict] = [
    {
        "timestamp": "Feb 22 00:05:38",
        "hostname": "SYSSVR1",
        "daemon": "systemd",
        "severity": "INFO",
        "message": "Started OpenBSD Secure Shell server."
    },
    {
        "timestamp": "Feb 22 00:06:15",
        "hostname": "SYSSVR2",
        "daemon": "kernel",
        "severity": "WARNING",
        "message": "Out of memory: Kill process 1234"
    },
    # ... more logs
]
```

### Schema Definition

```json
{
  "timestamp": {
    "type": "string",
    "format": "RFC 3164 format (MMM DD HH:MM:SS)",
    "example": "Feb 22 00:05:38"
  },
  "hostname": {
    "type": "string",
    "description": "Source hostname",
    "example": "SYSSVR1"
  },
  "daemon": {
    "type": "string",
    "description": "Process/daemon name",
    "example": "systemd"
  },
  "severity": {
    "type": "enum",
    "values": ["EMERG", "ALERT", "CRIT", "ERR", "WARNING", "NOTICE", "INFO", "DEBUG"],
    "example": "INFO"
  },
  "message": {
    "type": "string",
    "description": "Log message content",
    "example": "Service started successfully"
  }
}
```

### Access Patterns

**Read Access (Queries):**
```
get_all_logs()
  ├─ Acquire RLock
  ├─ Copy list
  └─ Release lock
  
Time: O(n) where n = number of logs

Filter Operations (implicit):
  for log in logs:
    if matches_criteria(log):
        result.append(log)
  Time: O(n) per query
```

**Write Access (Ingest):**
```
add_logs(logs)
  ├─ Acquire RLock (exclusive)
  ├─ Extend list (with validation)
  │  └─ Parse each line
  │  └─ Create dict
  │  └─ Append to list
  └─ Release lock
  
Time: O(m) where m = logs being added
```

**Purge (Nuclear):**
```
purge()
  ├─ Acquire RLock (exclusive)
  ├─ Clear entire list
  └─ Release lock
  
Time: O(1)
```

---

## 6. Client-Server Communication Protocol

### Protocol Design Goals

1. **Simplicity**: Pipe-delimited, human-readable format
2. **Stateless**: Each message is independent
3. **Extensible**: Easy to add new commands
4. **Unambiguous**: Clear request/response mapping

### Message Format

All messages use **pipe (|) delimiter**:

```
MESSAGE = COMMAND | PARAM1 | PARAM2 | ... | PARAMN
```

### Complete Protocol Specification

#### Request Messages

**INGEST (File Upload)**
```
Request:  UPLOAD|<filesize>|<file_content>
Example:  UPLOAD|1024|<Feb 22 00:05:38 SYSSVR1 systemd...>
Purpose:  Upload and parse syslog file
RespType: SUCCESS or ERROR
Lock:     WRITE (exclusive)
```

**SEARCH by Date**
```
Request:  QUERY|SEARCH_DATE|<date_string>
Example:  QUERY|SEARCH_DATE|Feb 22 00:0
Purpose:  Find logs matching date pattern
RespType: SUCCESS with formatted logs or ERROR
Lock:     READ
```

**SEARCH by Hostname**
```
Request:  QUERY|SEARCH_HOST|<hostname>
Example:  QUERY|SEARCH_HOST|SYSSVR1
Purpose:  Find logs from specific host
RespType: SUCCESS with formatted logs or ERROR
Lock:     READ
```

**SEARCH by Daemon**
```
Request:  QUERY|SEARCH_DAEMON|<daemon_name>
Example:  QUERY|SEARCH_DAEMON|systemd
Purpose:  Find logs from specific daemon
RespType: SUCCESS with formatted logs or ERROR
Lock:     READ
```

**SEARCH by Severity**
```
Request:  QUERY|SEARCH_SEVERITY|<level>
Example:  QUERY|SEARCH_SEVERITY|WARNING
Purpose:  Find logs with specific severity
RespType: SUCCESS with formatted logs or ERROR
Lock:     READ
```

**SEARCH by Keyword**
```
Request:  QUERY|SEARCH_KEYWORD|<keyword>
Example:  QUERY|SEARCH_KEYWORD|memory error
Purpose:  Find logs containing keyword
RespType: SUCCESS with formatted logs or ERROR
Lock:     READ
```

**COUNT Keyword**
```
Request:  QUERY|COUNT_KEYWORD|<keyword>
Example:  QUERY|COUNT_KEYWORD|failed
Purpose:  Count occurrences of keyword
RespType: SUCCESS|COUNT|<number> or ERROR
Lock:     READ
```

**PURGE (Delete All)**
```
Request:  ADMIN|PURGE
Purpose:  Clear entire database
RespType: SUCCESS or ERROR
Lock:     WRITE (exclusive)
```

**GET STATISTICS**
```
Request:  ADMIN|STATS
Purpose:  Retrieve database statistics
RespType: STATS|<stat_string> or ERROR
Lock:     READ
```

#### Response Messages

**Success Responses:**
```
SUCCESS|INGEST|<count> logs ingested
SUCCESS|QUERY|<formatted_logs>
SUCCESS|COUNT|<count>
SUCCESS|PURGE|All logs cleared
STATS|total: 1000 | hosts: 3 | daemons: 12
```

**Error Responses:**
```
ERROR|PARSE|Failed to parse log entry
ERROR|INVALID_COMMAND|Unknown command: X
ERROR|MALFORMED|Message format is incorrect
ERROR|IO|File I/O error: <details>
ERROR|INTERNAL|Server error: <details>
```

### Protocol State Machine

```
Client State:                 Server State:
─────────────                 ─────────────

DISCONNECTED
    ↓
CONNECT                      LISTENING
    ↓──────────────────────→ ACCEPT
    ↓                        ↓
CONNECTED                    WORKER SPAWNED
    ├─ INGEST  ──────────→   PARSE COMMAND
    │              ↓         PROCESS COMMAND
    │            RESPONSE    SEND RESPONSE
    │              ↓
    │ RECEIVE ←─────┘
    │    ↓
    │ PROCESS
    │
    ├─ QUERY ───────────→   (similar flow)
    │
    ├─ ADMIN ───────────→   (similar flow)
    │
    └─ QUIT
         ↓
    DISCONNECTED            WORKER EXITS
```

---

## 7. Error Handling & Recovery

### Error Categories

| Category | Examples | Recovery | Lock Status |
|----------|----------|----------|------------|
| **Parse Errors** | Invalid syslog format | Return ERROR, skip line | No lock acquired |
| **Protocol Errors** | Malformed message | Return ERROR, close connection | No lock acquired |
| **Concurrency Errors** | Dead worker | Remove from pool | Hold lock briefly |
| **I/O Errors** | File not found | Return ERROR | No lock acquired |
| **Logic Errors** | Invalid severity | Return ERROR | No lock acquired |

### Example Error Handling

```python
# In worker thread
try:
    message = socket.recv(65536)
    
except socket.timeout:
    logger.warning(f"Socket timeout for {addr}")
    break  # Disconnect
    
except socket.error as e:
    logger.error(f"Socket error for {addr}: {e}")
    break  # Disconnect
    
except Exception as e:
    response = ResponseFormatter.error_internal(str(e))
    try:
        socket.sendall(response.encode())
    except:
        pass
    break  # Disconnect
```

---

## 8. Performance Characteristics

### Time Complexity

| Operation | Complexity | Notes |
|-----------|-----------|-------|
| INGEST | O(m) | m = lines in file |
| SEARCH_HOST | O(n) | n = total logs |
| SEARCH_DATE | O(n) | n = total logs |
| COUNT_KEYWORD | O(n) | n = total logs |
| PURGE | O(1) | Clear operation |

### Space Complexity

| Structure | Complexity | Notes |
|-----------|-----------|-------|
| Log Storage | O(n) | n = number of logs |
| Timestamp | O(1) | Fixed-size string |
| Message | O(m) | m = message length |

### Lock Contention

**Best Case (Read-Heavy):**
- Many concurrent queries
- No writers
- Minimal lock wait time
- High parallelism

**Worst Case (Write-Heavy):**
- Continuous ingests (WRITE)
- Continuous purges (EXCLUSIVE WRITE)
- All readers blocked
- Single-threaded performance

**Typical Case:**
- Mix of reads and writes
- Short lock hold times (~ms)
- Good throughput

---

## 9. Scalability Considerations

### Current Limitations

1. **In-Memory Storage**: Loaded entirely in RAM
   - Limit: ~10GB on modern machine (50M logs @ 200B each)
   
2. **Single-Machine**: No distribution
   - Limit: OS file descriptors (~10K open connections)

3. **Linear Search**: No indexing
   - Limit: ~1ms per 1M logs for search

### Scalability Improvements

**Short-term (weeks):**
- Add SQLite for persistent storage
- Implement B-tree index on hostname/daemon
- Add pagination for large result sets

**Medium-term (months):**
- Distribute across multiple nodes
- Use message queue (RabbitMQ) for ingestion
- Implement log rotation/archival

**Long-term (years):**
- Full Elasticsearch-like distributed system
- Horizontal scaling to petabytes
- Real-time analytics engine

---

## 10. Testing Strategy

### Unit Tests

```python
# Test parsing
from syslog_parser import SyslogParser

log_line = "<134>Feb 22 00:05:38 HOST daemon: msg"
parsed = SyslogParser.parse_syslog(log_line)
assert parsed['hostname'] == 'HOST'
assert parsed['severity'] == 'INFO'
```

### Integration Tests

```python
# Test full pipeline
server = SyslogIndexerServer()
server.start()

client = SyslogForwarderClient()
client.connect()
client.ingest_file("sample_logs.txt")
results = client.search_host("SYSSVR1")
assert len(results) > 0
```

### Concurrency Tests

```python
# Test race conditions
import threading

storage = DataStorage()

def write():
    for i in range(1000):
        storage.add_logs([{"hostname": f"H{i}"}])

def read():
    for i in range(1000):
        logs = storage.get_all_logs()

t1 = threading.Thread(target=write)
t2 = threading.Thread(target=read)
t1.start()
t2.start()
t1.join()
t2.join()

# No race condition = test passes!
```

---

## References

### RFC & Standards

- **RFC 3164**: The BSD syslog Protocol
  https://tools.ietf.org/html/rfc3164

### Python Documentation

- **threading**: Thread-based parallelism
  https://docs.python.org/3/library/threading.html
  
- **socket**: Low-level networking interface
  https://docs.python.org/3/library/socket.html
  
- **re**: Regular expression operations
  https://docs.python.org/3/library/re.html

### Design Patterns

- **Thread-per-Connection**: Spawning threads per client
- **Critical Section**: Protecting shared mutable state
- **Mutual Exclusion**: Using locks for synchronization
- **Producer-Consumer**: Implicit (ingestion vs querying)

### Academic Resources

- "The Art of Multiprocessor Programming" - Herlihy & Shavit
- "Operating Systems: Three Easy Pieces" - Remzi and Andrea
- POSIX Threading documentation

---

## Conclusion

Mini-Splunk demonstrates fundamental server application design principles:

✓ **Concurrency**: Thread-per-connection model  
✓ **Synchronization**: RLock-based critical sections  
✓ **Architecture**: Modular, layered design  
✓ **Protocol**: Simple, unambiguous communication  
✓ **Robustness**: Error handling and recovery  

The system is production-ready for small-scale deployments and provides a solid foundation for more advanced log management systems.

---

**Document Version**: 1.0  
**Last Updated**: March 9, 2026  
**Course**: NSAPDEV - Server Application Development
