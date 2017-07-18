from celery.signals import worker_init


@worker_init.connect
def setup_exchanges(**kwargs):
    """ Setup result exchange to route all tasks to platform queue """
    from celery import app as _app

    app = _app.app_or_default()
    with app.producer_or_acquire() as P:
        # Ensure all queues are noticed and configured with their
        # appropriate exchange.
        for q in app.amqp.queues.values():
            P.maybe_declare(q)
