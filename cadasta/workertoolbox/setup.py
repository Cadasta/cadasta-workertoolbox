import logging
logger = logging.getLogger(__name__)


def limit_chord_unlock_tasks(app):
    """
    Set max_retries for chord.unlock tasks to avoid infinitely looping
    tasks. (see celery/celery#1700 or celery/celery#2725)
    """
    task = app.tasks['celery.chord_unlock']
    if task.max_retries is None:
        retries = getattr(app.conf, 'CHORD_UNLOCK_MAX_RETRIES', None)
        task.max_retries = retries


def setup_exchanges(app):
    """
    Setup result exchange to route all tasks to platform queue.
    """
    with app.producer_or_acquire() as P:
        # Ensure all queues are noticed and configured with their
        # appropriate exchange.
        for q in app.amqp.queues.values():
            P.maybe_declare(q)


SETUP_FUNCS = (
    limit_chord_unlock_tasks,
    setup_exchanges,
)


def setup_app(app, throw=False):
    """
    Ensure application is set up to expected configuration. This function is
    typically triggered by the worker_init signal, however it must be called
    manually by codebases that are run only as task producers or from within
    a Python shell.
    """
    for func in SETUP_FUNCS:
        try:
            func(app)
        except Exception:
            if throw:
                raise
            else:
                logger.exception(
                    "Failed to run setup function %r(app)", func.__name__)
