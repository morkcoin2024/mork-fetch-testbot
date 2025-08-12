# events.py
import threading
from collections import defaultdict, deque
import time, hashlib

class EventBus:
    def __init__(self, cache_size=2048, dedup_sec=300):
        self._subs = defaultdict(list)
        self._lock = threading.RLock()
        self._seen = deque(maxlen=cache_size)
        self._dedup_sec = dedup_sec

    def _make_key(self, topic:str, payload:dict):
        mint = (payload.get("mint") or payload.get("address") or "").lower()
        src = payload.get("source","").lower()
        t = int(payload.get("ts") or time.time())
        s = f"{topic}:{mint}:{src}:{t//self._dedup_sec}"
        return hashlib.sha1(s.encode()).hexdigest()

    def publish(self, topic:str, payload:dict):
        key = self._make_key(topic, payload)
        with self._lock:
            if key in self._seen: 
                return 0
            self._seen.append(key)
            subs = list(self._subs.get(topic, []))
        for fn in subs:
            try: fn(payload)
            except Exception as e: print(f"[EVENTBUS] subscriber error: {e}")
        return len(subs)

    def subscribe(self, topic:str=None, fn=None):
        """Subscribe to events - supports both new API (topic, fn) and old API (queue-based)"""
        if topic is None and fn is None:
            # Old API compatibility - return a queue for listening to all events
            import queue
            q = queue.Queue()
            # Subscribe to all topics with a function that puts events in the queue
            def queue_handler(payload):
                try:
                    q.put(payload, block=False)
                except:
                    pass  # Ignore full queue errors
            
            # Store reference to prevent garbage collection
            if not hasattr(self, '_queue_handlers'):
                self._queue_handlers = []
            self._queue_handlers.append(queue_handler)
            
            # Subscribe to common event types for backward compatibility
            for topic in ['scan.new', 'webhook.update', 'app.*']:
                with self._lock:
                    self._subs[topic].append(queue_handler)
            return q
        else:
            # New API - subscribe function to specific topic
            with self._lock:
                self._subs[topic].append(fn)

BUS = EventBus()

# Additional compatibility attributes
BUS.subscribers = set()  # Compatibility for old eventbus API
BUS.lock = BUS._lock     # Expose lock for compatibility