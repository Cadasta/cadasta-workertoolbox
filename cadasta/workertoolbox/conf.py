import os
import pprint

from kombu import Exchange, Queue

# Ensure signals are imported before app starts
from .signals import *  # NOQA
from . import DEFAULT_QUEUES


class Config:
    # Broker
    QUEUE_NAME_PREFIX = os.environ.get('QUEUE_PREFIX', 'dev')
    broker_transport = 'sqs'
    broker_transport_options = {
        'region': 'us-west-2',
        'queue_name_prefix': '{}-'.format(QUEUE_NAME_PREFIX)
    }

    # Results
    RESULT_DB_USER = os.environ.get('RESULT_DB_USER', 'cadasta')
    RESULT_DB_PASS = os.environ.get('RESULT_DB_PASS', 'cadasta')
    RESULT_DB_HOST = os.environ.get('RESULT_DB_HOST', 'localhost')
    RESULT_DB_NAME = os.environ.get('RESULT_DB_NAME', 'cadasta')
    RESULT_DB_PORT = os.environ.get('RESULT_DB_PORT', '5432')
    result_backend = (
        'db+postgresql://{0.RESULT_DB_USER}:{0.RESULT_DB_PASS}@'
        '{0.RESULT_DB_HOST}:{0.RESULT_DB_PORT}/{0.RESULT_DB_NAME}')
    task_track_started = True

    # Exchanges
    task_default_exchange = 'task_exchange'
    task_default_exchange_type = 'topic'

    # Queues
    PLATFORM_QUEUE_NAME = 'platform.fifo'

    # Tasks
    CHORD_UNLOCK_MAX_RETRIES = 60 * 60 * 6  # 6hrs

    def __init__(self, QUEUES=DEFAULT_QUEUES, imports=('app.tasks',), **kw):
        """
        Object to manage Celery application configuration.
        """
        self.QUEUES = QUEUES
        self.imports = imports

        for k, v in kw.items():
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
            self.task_routes = self._route_task

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

    @property
    def _default_exchange_obj(self):
        return Exchange(
            self.task_default_exchange,
            self.task_default_exchange_type)

    @staticmethod
    def _generate_queues(queues, exchange, platform_queue):
        """ Queues known by this worker """
        return set([
            Queue('celery', exchange, routing_key='celery'),
            Queue(platform_queue, exchange, routing_key='#'),
        ] + [
            Queue(q_name, exchange, routing_key=q_name)
            for q_name in queues
        ])

    def _route_task(self, name, args, kwargs, options, task=None, **kw):
        return {
            'routing_key': name.split('.')[0],
            'exchange': self._default_exchange_obj
        }
