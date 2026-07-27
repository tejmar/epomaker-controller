import time


class TimeHelper:
    """Enforce a minimum elapsed time, deterministically.

    Use as a context manager around the work to be paced::

        with TimeHelper(1.6):
            do_paced_work()

    On a clean exit it sleeps for whatever remains of ``min_duration``. This
    replaces the previous ``__del__``-based timing, which depended on
    non-deterministic garbage collection for correctness.
    """

    def __init__(self, min_duration: float) -> None:
        self.min_duration = min_duration
        self.start_time = time.time()

    def wait(self) -> None:
        """Sleep for whatever remains of the minimum duration."""
        remaining = self.min_duration - (time.time() - self.start_time)
        if remaining > 0:
            time.sleep(remaining)

    def __enter__(self) -> "TimeHelper":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Only enforce the minimum duration on a clean exit; if an exception
        # (e.g. KeyboardInterrupt) is propagating, don't delay it.
        if exc_type is None:
            self.wait()
