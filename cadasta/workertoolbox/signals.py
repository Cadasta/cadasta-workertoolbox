from celery.signals import worker_init


@worker_init.connect
def setup_exchanges(sender, **kwargs):
    """ Setup result exchange to route all tasks to platform queue """
    app = sender.app
    with app.producer_or_acquire() as P:
        # Ensure all queues are noticed and configured with their
        # appropriate exchange.
        for q in app.amqp.queues.values():
            P.maybe_declare(q)


@worker_init.connect
def limit_chord_unlock_tasks(sender, **kwargs):
    """
    Set max_retries for chord.unlock tasks to avoid infinitely looping
    tasks. (see celery/celery#1700 or celery/celery#2725)
    """
    task = sender.app.tasks['celery.chord_unlock']
    if task.max_retries is None:
        retries = getattr(sender.app.conf, 'CHORD_UNLOCK_MAX_RETRIES', None)
        task.max_retries = retries
