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
            'class': 'cadasta.workertoolbox.logging.ColorFormatter'
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
    # Broker
    QUEUE_NAME_PREFIX = env.get('QUEUE_PREFIX', 'dev')
    broker_transport = 'sqs'
    broker_transport_options = {
        'region': 'us-west-2',
        'queue_name_prefix': '{}-'.format(QUEUE_NAME_PREFIX)
    }

    # Results
    RESULT_DB_USER = env.get('RESULT_DB_USER', 'worker')
    RESULT_DB_PASS = env.get('RESULT_DB_PASS', 'cadasta')
    RESULT_DB_HOST = env.get('RESULT_DB_HOST', 'localhost')
    RESULT_DB_NAME = env.get('RESULT_DB_NAME', 'cadasta')
    RESULT_DB_PORT = env.get('RESULT_DB_PORT', '5432')
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

    def __init__(self, QUEUES=DEFAULT_QUEUES, imports=('app.tasks',),
                 SETUP_LOGGING=True, **kw):
        """
        Object to manage Celery application configuration.
        """
        self.QUEUES = QUEUES
        self.imports = imports

        for k, v in kw.items():
            setattr(self, k, v)

        if SETUP_LOGGING:
            self.setup_default_logging()
            self.worker_hijack_root_logger = False

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
