# eventbus.py
from __future__ import annotations
import time, json, threading, queue

class EventBus:
    def __init__(self, maxsize=2000):
        self.q = queue.Queue(maxsize=maxsize)
        self.subscribers = set()
        self.lock = threading.Lock()

    def publish(self, typ: str, payload: dict | None = None):
        evt = {
            "ts": int(time.time() * 1000),
            "type": typ,
            "data": payload or {},
        }
        try: self.q.put_nowait(evt)
        except queue.Full:
            # drop oldest-ish by draining a few
            for _ in range(20):
                try: self.q.get_nowait()
                except queue.Empty: break
            self.q.put_nowait(evt)
        # fanout to live subscribers (non-blocking)
        with self.lock:
            dead = []
            for s in list(self.subscribers):
                try: s.put_nowait(evt)
                except queue.Full:
                    dead.append(s)
            for s in dead:
                self.subscribers.discard(s)

    def subscribe(self):
        q = queue.Queue(maxsize=500)
        with self.lock: self.subscribers.add(q)
        return q

BUS = EventBus()
def publish(typ, payload=None): BUS.publish(typ, payload)
def get_subscriber_count(): 
    with BUS.lock: 
        return len(BUS.subscribers)