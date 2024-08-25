import os

# See https://docs.gunicorn.org/en/stable/settings.html for
# explanations of settings

bind = f'{os.getenv("PAPERLESS_BIND_ADDR", "[::]")}:{os.getenv("PAPERLESS_PORT", 8000)}'

workers = int(os.getenv("PAPERLESS_WEBSERVER_WORKERS", 1))
worker_class = "paperless.workers.ConfigurableWorker"
timeout = 120
preload_app = True

# https://docs.gunicorn.org/en/stable/faq.html#blocking-os-fchmod
worker_tmp_dir = "/dev/shm"


def pre_fork(server, worker):
    pass


def pre_exec(server):
    server.log.info("Forked child, re-executing.")


def when_ready(server):
    server.log.info("Server is ready. Spawning workers")


def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

    ## get traceback info
    import sys
    import threading
    import traceback

    id2name = {th.ident: th.name for th in threading.enumerate()}
    code = []
    for threadId, stack in sys._current_frames().items():
        code.append(f"\n# Thread: {id2name.get(threadId, '')}({threadId})")
        for filename, lineno, name, line in traceback.extract_stack(stack):
            code.append(f'File: "{filename}", line {lineno}, in {name}')
            if line:
                code.append(f"  {line.strip()}")
    worker.log.debug("\n".join(code))


def worker_abort(worker):
    worker.log.info("worker received SIGABRT signal")
