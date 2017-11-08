from ast import literal_eval
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
    def __init__(self, **kw):
        """
        Object to manage Celery application configuration.
        """
        self.ENV_PREFIX = kw.get(
            'ENV_PREFIX', env.get('CELERY_ENV_PREFIX', 'CELERY_'))

        # Assign any keyword argument to object
        for k, v in kw.items():
            setattr(self, k, v)

        # Configure Broker
        self.set('QUEUE_PREFIX', 'dev')
        self.set('broker_transport', 'sqs')
        self.set('broker_transport_options', {
                'region': 'us-west-2',
                'queue_name_prefix': '{}-'.format(self.QUEUE_PREFIX),

                # Ensure long-polling for SQS messages
                'wait_time_seconds': 20,
                # Wait up to 20 seconds for msg ack from worker (if
                # creating queue)
                'visibility_timeout': 20,
                # Retry immediately if cannot connect to SQS once
                'interval_start': 0,
                # Ensure error is raised if cannot connect to SQS twice
                'max_retries': 1,
            })

        # Setup Logging
        self.set('task_track_started', True)
        if self.set('SETUP_FILE_LOGGING', False):
            self.setup_file_logging()

        opbeat_env_vars = [
            env.get('OPBEAT_ORGANIZATION_ID'), env.get('OPBEAT_APP_ID'),
            env.get('OPBEAT_SECRET_TOKEN'),
        ]
        if self.set('SETUP_OPBEAT_LOGGING', all(opbeat_env_vars)):
            assert all(opbeat_env_vars), (
                'Not all required env variables for Opbeat logging are set'
            )
            self.setup_opbeat_logging()

        # Configure Result Backend
        self.set('RESULT_DB_USER', 'worker')
        self.set('RESULT_DB_PASS', 'cadasta')
        self.set('RESULT_DB_HOST', 'localhost')
        self.set('RESULT_DB_NAME', 'cadasta')
        self.set('RESULT_DB_PORT', '5432')
        self.set('result_backend', (
            'db+postgresql://{0.RESULT_DB_USER}:{0.RESULT_DB_PASS}@'
            '{0.RESULT_DB_HOST}:{0.RESULT_DB_PORT}/{0.RESULT_DB_NAME}'))
        try:
            self.result_backend = self.result_backend.format(self)
        except ValueError:
            raise ValueError(
                "Unable to render 'result_backend' value: %r" %
                self.result_backend)

        # Configure Routes & Exchanges
        self.set('task_default_exchange', 'task_exchange')
        self.set('task_default_exchange_type', 'topic')
        self.set('task_routes', self._route_task, from_env=False)

        # Configure Queues
        self.set('QUEUES', DEFAULT_QUEUES)
        self.set('PLATFORM_QUEUE_NAME', 'platform.fifo')
        if not hasattr(self, 'task_queues'):
            self.task_queues = self._generate_queues(
                self.QUEUES, self._default_exchange_obj,
                self.PLATFORM_QUEUE_NAME)

        # Configure Tasks
        self.set('imports', ('app.tasks',))
        self.set('CHORD_UNLOCK_MAX_RETRIES', 60 * 60 * 6)  # 6 hrs

        # Assign any other matching env variables to object
        for k, v in env.items():
            if not k.startswith(self.ENV_PREFIX):
                continue
            key = k.split(self.ENV_PREFIX, 1)[1].lower()
            if hasattr(self, key.lower()) or hasattr(self, key.upper()):
                continue
            if key in ('log_level', 'log_file'):  # Ignore Celery-set env vars
                continue
            setattr(self, key, v)

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

    def set(self, keyword, default, from_env=True):
        """
        Set value on self if not already set. If unset, attempt to
        retrieve from environment variable of same name (unless disabled
        via 'from_env'). If 'default' value is not a string, evaluate
        environment variable as a Python type. If no env variables are
        found, fallback to 'default' value.
        """
        env_key = '{}{}'.format(self.ENV_PREFIX, keyword.upper())
        if hasattr(self, keyword):
            return getattr(self, keyword)
        value = default
        if from_env and (env_key in env):
            env_val = env.get(env_key)
            should_eval = not isinstance(default, str)
            try:
                value = literal_eval(env_val) if should_eval else env_val
            except (ValueError, SyntaxError):
                raise ValueError("Unable to cast %r to %r" % (
                    env_val, type.__name__))
        setattr(self, keyword, value)
        return getattr(self, keyword)

    def setup_file_logging(self, config=DEFAULT_LOGGING_CONFIG):
        self.set('worker_hijack_root_logger', False)
        logging.config.dictConfig(config)

    def setup_opbeat_logging(self, opbeat_client=None):
        self._opbeat_client = opbeat_client or Client()
        self.setup_opbeat_log_handler(self._opbeat_client)
        self.setup_opbeat_task_signal(self._opbeat_client)

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
