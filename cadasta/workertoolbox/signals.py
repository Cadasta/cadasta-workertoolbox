from celery.signals import worker_init

from .setup import setup_app


@worker_init.connect
def setup_app_signal_handler(sender, **kwargs):
    setup_app(sender.app, throw=False)
