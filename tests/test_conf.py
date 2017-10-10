import unittest
from unittest.mock import patch, MagicMock

from opbeat import Client

from cadasta.workertoolbox.conf import Config


class TestConfigClass(unittest.TestCase):

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
        self.assertEqual(
            Config(['bar']).QUEUES,
            ['bar'])

    def test_backend_default(self):
        self.assertEqual(
            Config(QUEUES=[]).result_backend,
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

    @patch('cadasta.workertoolbox.conf.env', {'OPBEAT_ORGANIZATION_ID': 123})
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_log_handler')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_task_signal')
    def test_setup_opbeat_tools(self, task_signal, log_handler, Client):
        """ Ensure opbeat logging is called if env variable is set """
        Config()
        Client.assert_called_once_with()
        task_signal.assert_called_once_with(Client.return_value)
        log_handler.assert_called_once_with(Client.return_value)

    @patch('cadasta.workertoolbox.conf.env', {'OPBEAT_ORGANIZATION_ID': 123})
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_log_handler')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_task_signal')
    def test_setup_opbeat_tools_override(self, task_signal, log_handler, Client):
        """
        Ensure opbeat logging is not called if env variable is set but setup
        is set to false
        """
        Config(SETUP_LOGGING=False)
        self.assertFalse(Client.called)
        self.assertFalse(task_signal.called)
        self.assertFalse(log_handler.called)

    @patch('cadasta.workertoolbox.conf.env', {})
    @patch('cadasta.workertoolbox.conf.Client')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_log_handler')
    @patch('cadasta.workertoolbox.conf.Config.setup_opbeat_task_signal')
    def test_setup_opbeat_tools_not_called(self, task_signal, log_handler, Client):
        """ Ensure opbeat logging is called if env variable is set """
        Config()
        self.assertFalse(Client.called)
        self.assertFalse(task_signal.called)
        self.assertFalse(log_handler.called)

    @patch('cadasta.workertoolbox.conf.logging')
    def test_setup_opbeat_log_handler(self, logging):
        """ Ensure opbeat logging handler adds handler to base logger """
        client = Client()
        Config.setup_opbeat_log_handler(client)
        logging.getLogger.assert_called_once_with('')
        logger = logging.getLogger.return_value
        self.assertEqual(logger.addHandler.call_count, 1)
        self.assertEqual(
            logger.addHandler.call_args_list[0][0][0].__class__.__name__,
            'OpbeatHandler')

    @patch('cadasta.workertoolbox.conf.logging')
    def test_setup_opbeat_log_handler_custom(self, logging):
        """ Ensure opbeat logging handler adds handler to custom logger """
        client = Client()
        Config.setup_opbeat_log_handler(client, 'foo')
        logging.getLogger.assert_called_once_with('foo')
        logger = logging.getLogger.return_value
        self.assertEqual(logger.addHandler.call_count, 1)
        self.assertEqual(
            logger.addHandler.call_args_list[0][0][0].__class__.__name__,
            'OpbeatHandler')

    @patch('cadasta.workertoolbox.conf.register_signal')
    def test_setup_opbeat_task_signal(self, register_signal):
        """ Ensure opbeat task handler calls opbeat signal setup function """
        client = Client()
        Config.setup_opbeat_task_signal(client)
        register_signal.assert_called_once_with(client)
