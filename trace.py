import time

class TraceSpan:
    def __init__(self, name: str):
        self.name = name
        self.events = []
        self.status = "ok"
        self.start = time.time()
        self.duration_ms = 0
        self._data = {}
    def add_event(self, name: str, data: dict = None):
        self.events.append({"name": name, "data": data or {}})
    def __enter__(self): return self
    def __exit__(self, *args): self.duration_ms = (time.time() - self.start) * 1000

class AgentTracer:
    def __init__(self): self._traces = []
    def trace(self, name: str, **kwargs):
        span = TraceSpan(name)
        span._data = kwargs
        self._traces.append(span)
        return span
    def list_traces(self, limit: int = 10):
        return [{"name": t.name, "duration_ms": t.duration_ms, "status": t.status, "events": t.events} for t in self._traces[-limit:]]

agent_tracer = AgentTracer()
