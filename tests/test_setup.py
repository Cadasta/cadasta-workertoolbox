import unittest
from mock import MagicMock, patch

from celery import Celery

from cadasta.workertoolbox import setup


def mock_setup_func(success=True):
    if success:
        return MagicMock(return_value=True)
    return MagicMock(
        side_effect=AttributeError("Uh oh!"), __name__='SetupFuncB')


class TestSetup(unittest.TestCase):
    @patch('cadasta.workertoolbox.setup.SETUP_FUNCS',
           (mock_setup_func(True), mock_setup_func(False)))
    @patch('cadasta.workertoolbox.setup.logger')
    def test_caught_failures(self, logger):
        app = Celery()
        setup.setup_app(app, throw=False)

        from cadasta.workertoolbox.setup import SETUP_FUNCS
        for func in SETUP_FUNCS:
            func.assert_called_once_with(app)

        logger.exception.assert_called_once_with(
            'Failed to run setup function %r(app)', 'SetupFuncB')

        self.assertFalse(app.is_set_up)

    @patch('cadasta.workertoolbox.setup.SETUP_FUNCS',
           (mock_setup_func(True), mock_setup_func(False)))
    @patch('cadasta.workertoolbox.setup.logger')
    def test_thrown_failures(self, logger):
        app = Celery()
        with self.assertRaises(AttributeError):
            setup.setup_app(app, throw=True)

        from cadasta.workertoolbox.setup import SETUP_FUNCS
        for func in SETUP_FUNCS:
            SETUP_FUNCS[0].assert_called_once_with(app)

        self.assertFalse(logger.exception.called)
        self.assertFalse(app.is_set_up)

    @patch('cadasta.workertoolbox.setup.SETUP_FUNCS',
           (mock_setup_func(True), mock_setup_func(True)))
    @patch('cadasta.workertoolbox.setup.logger')
    def test_no_failures(self, logger):
        app = Celery()
        setup.setup_app(app, throw=True)

        from cadasta.workertoolbox.setup import SETUP_FUNCS
        for func in SETUP_FUNCS:
            SETUP_FUNCS[0].assert_called_once_with(app)

        self.assertFalse(logger.exception.called)
        self.assertTrue(app.is_set_up)
