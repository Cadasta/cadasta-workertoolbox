from os import environ as env
import pprint
import logging
import logging.config

from kombu import Exchange, Queue
from opbeat import Client
from opbeat.contrib.celery import register_signal
from opbeat.handlers.logging import OpbeatHandler

# Ensure signals are imported before app starts
from .signals import *  # NOQA
from . import DEFAULT_QUEUES


DEFAULT_LOGGING_FMT = '[%(asctime)s: %(levelname)s/%(processName)s %(message)s'
DEFAULT_LOGGING_CONFIG = {
    'version': 1,
    'formatters': {
        'colored': {
            'format': DEFAULT_LOGGING_FMT,
            'class': 'cadasta.workertoolbox.utils.ColorFormatter'
        },
        'default': {
            'format': DEFAULT_LOGGING_FMT,
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'colored',
        },
        'info_file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': 'app.info.log',
            'backupCount': 2,
            'maxBytes': 1024 * 1024 * 5,
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'default',
            'filename': 'app.error.log',
            'backupCount': 2,
            'maxBytes': 1024 * 1024 * 5,
        },
    },
    'loggers': {
        '': {
            'handlers': ['console', 'info_file', 'error_file'],
        },
    }
}


class Config:

    def __init__(self, QUEUES=DEFAULT_QUEUES, imports=('app.tasks',),
                 SETUP_LOGGING=True, **kw):
        """
        Object to manage Celery application configuration.
        """
        self.QUEUES = QUEUES
        self.imports = imports

        # Assign any keyword argument to object
        for k, v in kw.items():
            setattr(self, k, v)

        # Configure Broker
        self.QUEUE_PREFIX = self.args_or_env('QUEUE_PREFIX', 'dev')
        self.broker_transport = self.args_or_env('broker_transport', 'sqs')
        self.broker_transport_options = getattr(
            self, 'broker_transport_options', {
                'region': 'us-west-2',
                'queue_name_prefix': '{}-'.format(self.QUEUE_PREFIX),

                'wait_time_seconds': 20,  # Ensure long-polling for SQS messages            # NOQA
                'visibility_timeout': 20,  # Wait up to 20 seconds for msg ack from worker  # NOQA
                'max_retries': 1,  # Ensure error is raised if cannot connect to SQS twice  # NOQA
                'interval_start': 0,  # Retry immediately if cannot connect to SQS once     # NOQA
            })

        # Setup Logging
        self.task_track_started = True
        if SETUP_LOGGING:
            self.setup_default_logging()
            self.worker_hijack_root_logger = False

        # Configure Result Backend
        self.RESULT_DB_USER = self.args_or_env('RESULT_DB_USER', 'worker')
        self.RESULT_DB_PASS = self.args_or_env('RESULT_DB_PASS', 'cadasta')
        self.RESULT_DB_HOST = self.args_or_env('RESULT_DB_HOST', 'localhost')
        self.RESULT_DB_NAME = self.args_or_env('RESULT_DB_NAME', 'cadasta')
        self.RESULT_DB_PORT = self.args_or_env('RESULT_DB_PORT', '5432')
        self.result_backend = self.args_or_env('result_backend', (
            'db+postgresql://{0.RESULT_DB_USER}:{0.RESULT_DB_PASS}@'
            '{0.RESULT_DB_HOST}:{0.RESULT_DB_PORT}/{0.RESULT_DB_NAME}'))
        try:
            self.result_backend = self.result_backend.format(self)
        except ValueError:
            raise ValueError(
                "Unable to render 'result_backend' value: %r" %
                self.result_backend)

        # Configure Routes & Exchanges
        self.task_default_exchange = 'task_exchange'
        self.task_default_exchange_type = 'topic'
        if not hasattr(self, 'task_routes'):
            self.task_routes = self._route_task

        # Configure Queues
        self.PLATFORM_QUEUE_NAME = self.args_or_env(
            'PLATFORM_QUEUE_NAME', 'platform.fifo')
        if not hasattr(self, 'task_queues'):
            self.task_queues = self._generate_queues(
                self.QUEUES, self._default_exchange_obj,
                self.PLATFORM_QUEUE_NAME)

        # Configure Tasks
        self.CHORD_UNLOCK_MAX_RETRIES = int(self.args_or_env(
            'CHORD_UNLOCK_MAX_RETRIES', 60 * 60 * 6))  # 6hrs

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

    def args_or_env(self, keyword, default=None):
        if hasattr(self, keyword):
            return getattr(self, keyword)
        return env.get(keyword, default)

    def setup_default_logging(self, opbeat_client=None):
        self.setup_log_files()
        if opbeat_client or env.get('OPBEAT_ORGANIZATION_ID'):
            self._opbeat_client = opbeat_client or Client()
            self.setup_opbeat_log_handler(self._opbeat_client)
            self.setup_opbeat_task_signal(self._opbeat_client)

    @staticmethod
    def setup_log_files(config=DEFAULT_LOGGING_CONFIG):
        logging.config.dictConfig(config)

    @staticmethod
    def setup_opbeat_log_handler(client, logger='', level=logging.ERROR):
        """
        Add OpBeat as log handler. Defaults to attaching to root logger
        and handling logs of level ERROR and above.
        """
        logger = logging.getLogger(logger)
        handler = OpbeatHandler(client)
        handler.setLevel(level)
        logger.addHandler(handler)

    @staticmethod
    def setup_opbeat_task_signal(client):
        """
        Setup OpBeat to handle Celery task failures.
        """
        register_signal(client)

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
