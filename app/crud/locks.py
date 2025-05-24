from contextlib import asynccontextmanager

LOCKS = dict()

@asynccontextmanager
async def acquire_locks(*locks):
    try:
        yield
    finally:
        pass
