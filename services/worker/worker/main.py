"""Worker composition root.

Concrete provider wiring is intentionally deferred until the first real provider is added.
The reusable polling loop lives in services.worker.worker.runtime.
"""

from services.worker.worker.runtime import run_once, run_worker

__all__ = ["run_once", "run_worker"]
