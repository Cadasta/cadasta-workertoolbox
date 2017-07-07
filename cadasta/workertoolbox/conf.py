import os
import pprint

from kombu import Exchange, Queue

# Ensure signals are imported before app starts
from .signals import *  # NOQA


class Config:
    # Broker
    prefix = os.environ.get('QUEUE_PREFIX', 'dev')
    broker_transport = 'sqs'
    broker_transport_options = {
        'region': 'us-west-2',
        'queue_name_prefix': '{}-'.format(prefix)
    }
    worker_prefetch_multiplier = 0  # https://github.com/celery/celery/issues/3712  # noqa

    # Results
    RESULT_DB_USER = os.environ.get('RESULT_DB_USER', 'cadasta')
    RESULT_DB_PASS = os.environ.get('RESULT_DB_PASS', 'cadasta')
    RESULT_DB_HOST = os.environ.get('RESULT_DB_HOST', 'localhost')
    RESULT_DB_NAME = os.environ.get('RESULT_DB_NAME', 'cadasta')
    result_backend = (
        'db+postgresql://{0.RESULT_DB_USER}:{0.RESULT_DB_PASS}@'
        '{0.RESULT_DB_HOST}/{0.RESULT_DB_NAME}')
    task_track_started = True

    # Exchanges
    task_default_exchange = 'task_exchange'
    task_default_exchange_type = 'topic'

    _default_exchange_obj = Exchange(
        task_default_exchange, task_default_exchange_type)

    # Queues
    PLATFORM_QUEUE_NAME = 'platform.fifo'

    def __init__(self, queues, imports=('app.tasks',), **kwargs):
        """
        Object to manage Celery application configuration.
        """
        self.QUEUES = queues
        self.imports = imports

        for k, v in kwargs.items():
            setattr(self, k, v)

        try:
            self.result_backend = self.result_backend.format(self)
        except ValueError:
            raise ValueError(
                "Unable to render 'result_backend' value: %r" %
                self.result_backend)

        if not hasattr(self, 'task_queues'):
            self.task_queues = self._generate_queues(
                self.QUEUES, self._default_exchange_obj,
                self.PLATFORM_QUEUE_NAME)

        if not hasattr(self, 'task_routes'):
            self.task_routes = self._generate_routes(
                self.QUEUES, self._default_exchange_obj)

    def __repr__(self):
        attr_str = pprint.pformat(self.to_dict())
        return '{0.__class__.__name__}({1})'.format(self, attr_str)

    def to_dict(self):
        return {
            k: getattr(self, k)
            for k in dir(self)
            if (k.islower() and not k.startswith('_') and
                not callable(getattr(self, k)))
        }

    @staticmethod
    def _generate_queues(queues, exchange, platform_queue):
        """ Queues known by this worker """
        return set((
            Queue('celery', exchange, routing_key='celery'),
            Queue(platform_queue, exchange, routing_key='#'),
        ) + tuple(
            Queue(q_name, exchange, routing_key=q_name)
            for q_name in queues
        ))

    @staticmethod
    def _generate_routes(queues, exchange):
        """
        Associate specific task names or task name patterns to an
        exchange and routing key
        """
        routes = {
            'celery.*': {
                'exchange': exchange,
                'routing_key': 'celery',
            },
        }
        for q in queues:
            routes.setdefault('{}.*'.format(q), {
                'exchange': exchange,
                'routing_key': q,
            })
        return routes
