import logging
import unittest
from mock import patch

from cadasta.workertoolbox.conf import Config


class TestConfigClass(unittest.TestCase):

    @patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': '9876'})
    def test_set_env_vars(self):
        """
        Ensure that sets any CELERY_* env var to object
        """
        conf = Config()
        self.assertEqual(conf.foo, '9876')

    @patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': '9876'})
    def test_set_no_overwrite_uppercase(self):
        """
        Ensure that any CELERY_* env var won't be set to object if
        uppercase version already exists on object.
        """
        conf = Config(FOO='1234')
        self.assertFalse(hasattr(conf, 'foo'))
        self.assertEqual(conf.FOO, '1234')

    @patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': '9876'})
    def test_set_no_overwrite(self):
        """
        Ensure that sets to provide init keyword argument instead of env
        variable or function 'default' argument
        """
        conf = Config(foo=1234)
        conf.set('foo', 5678)
        self.assertEqual(conf.foo, 1234)

    @patch('cadasta.workertoolbox.conf.env', {})
    def test_set_uses_default(self):
        """
        Ensure uses function 'default' argument if no env or preset value
        """
        conf = Config()
        conf.set('foo', 1234)
        self.assertEqual(conf.foo, 1234)

    def test_set_uses_env(self):
        """
        Ensure that if the 'default' is a string, won't evaluate env variable
        """
        conf = Config()
        with patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': 'False'}):
            conf.set('foo', True)
        self.assertEqual(conf.foo, False)

    def test_set_no_eval(self):
        """
        Ensure that if the 'default' is a string, won't evaluate env variable
        """
        conf = Config()
        with patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': 'False'}):
            conf.set('foo', 'True')
        self.assertEqual(conf.foo, 'False')

    def test_set_bad_env_val(self):
        """
        Ensure error is thrown if the 'default' is a string, and env
        variable is not evaluatable value
        """
        conf = Config()
        with patch('cadasta.workertoolbox.conf.env', {'CELERY_FOO': ''}):
            with self.assertRaises(ValueError):
                conf.set('foo', True)

    def test_override(self):
        """ Ensure default params can be overridden """
        conf = Config(broker_transport='foo')
        self.assertEqual(conf.broker_transport, 'foo')

    def test_repr(self):
        conf = Config(a=1, b=2, z=3)
        self.assertTrue(repr(conf).startswith("Config({'a': 1,\n 'b': 2,\n"))
        self.assertTrue(repr(conf).endswith(" 'z': 3})"))

    def test_queues(self):
        self.assertEqual(
            Config(QUEUES=['foo']).QUEUES,
            ['foo'])

    def test_backend_default(self):
        self.assertEqual(
            Config().result_backend,
            'db+postgresql://worker:cadasta@localhost:5432/cadasta')

    def test_backend_custom(self):
        self.assertEqual(
            Config(result_backend=':memory:').result_backend,
            ':memory:')

    def test_backend_custom_rendered(self):
        self.assertEqual(
            Config(
                result_backend='{0.foo}:{0.BAR}',
                foo='abc', BAR='def'
            ).result_backend,
            'abc:def'
        )

    def test_backend_custom_error(self):
        with self.assertRaises(ValueError) as context:
            Config(
                result_backend='{0.foo}:{}',
                foo='abc'
            )
        self.assertEqual(
            getattr(context.exception, 'message', context.exception.args[0]),
            "Unable to render 'result_backend' value: '{0.foo}:{}'"
        )

    def test_default_chord_unlock_max_retries(self):
        conf = Config()
        self.assertTrue(isinstance(conf.CHORD_UNLOCK_MAX_RETRIES, int))

    @patch('cadasta.workertoolbox.conf.Config.setup_file_logging')
    def test_default_no_setup_file_logging(self, setup_file_logging):
        Config()
        self.assertFalse(setup_file_logging.called)

    @patch('cadasta.workertoolbox.conf.Config.setup_file_logging')
    def test_setup_file_logging_argument(self, setup_file_logging):
        Config(SETUP_FILE_LOGGING=True)
        setup_file_logging.assert_called_once_with()

    @patch('cadasta.workertoolbox.conf.logging')
    def test_setup_file_logging(self, logging):
        my_logging_config = {}
        Config(SETUP_FILE_LOGGING=False).setup_file_logging(my_logging_config)
        logging.config.dictConfig.assert_called_once_with(my_logging_config)

    @patch('cadasta.workertoolbox.conf.env', {
        'SENTRY_DSN': 'https://example.com',
        'SENTRY_NAME': 'foo',
        'SENTRY_ENVIRONMENT': 'bar',
        'SENTRY_RELEASE': '987',
    })
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.register_logger_signal')
    @patch('cadasta.workertoolbox.conf.register_signal')
    def test_setup_sentry_tools(self, register_signal, logger_signal, Client):
        """ Ensure sentry logging is called if env variable is set """
        Config()
        Client.assert_called_once_with(
            dsn='https://example.com',
            name='foo',
            environment='bar',
            release='987',
        )
        logger_signal.assert_called_once_with(Client.return_value, loglevel=logging.ERROR)
        register_signal.assert_called_once_with(Client.return_value)

    @patch('cadasta.workertoolbox.conf.env', {'SENTRY_DSN': 'https://example.com'})
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.register_logger_signal')
    @patch('cadasta.workertoolbox.conf.register_signal')
    def test_setup_sentry_tools_override(self, register_signal, logger_signal, Client):
        """
        Ensure sentry logging is not called if env variable is set but setup
        is set to false
        """
        Config(SETUP_SENTRY_LOGGING=False)
        self.assertFalse(Client.called)
        self.assertFalse(register_signal.called)
        self.assertFalse(logger_signal.called)

    @patch('cadasta.workertoolbox.conf.env', {})
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.register_logger_signal')
    @patch('cadasta.workertoolbox.conf.register_signal')
    def test_setup_sentry_tools_not_called(self, register_signal, logger_signal, Client):
        """
        Ensure sentry logging is not called if sentry env variabels are unset
        """
        Config()
        self.assertFalse(Client.called)
        self.assertFalse(register_signal.called)
        self.assertFalse(logger_signal.called)
