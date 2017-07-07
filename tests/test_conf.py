import unittest

from cadasta.workertoolbox.conf import Config


class TestConfigClass(unittest.TestCase):

    def test_override(self):
        """ Ensure default params can be overridden """
        conf = Config(queues=[], broker_transport='foo')
        self.assertEqual(conf.broker_transport, 'foo')

    def test_repr(self):
        conf = Config(queues=[], a=1, b=2, z=3)
        self.assertTrue(repr(conf).startswith("Config({'a': 1,\n 'b': 2,\n"))
        self.assertTrue(repr(conf).endswith(" 'z': 3})"))

    def test_queues(self):
        self.assertEqual(
            Config(queues=['foo']).QUEUES,
            ['foo'])
        self.assertEqual(
            Config(['bar']).QUEUES,
            ['bar'])

    def test_backend_default(self):
        self.assertEqual(
            Config(queues=[]).result_backend,
            'db+postgresql://cadasta:cadasta@localhost/cadasta')

    def test_backend_custom(self):
        self.assertEqual(
            Config(queues=[], result_backend=':memory:').result_backend,
            ':memory:')

    def test_backend_custom_rendered(self):
        self.assertEqual(
            Config(
                queues=[], result_backend='{0.foo}:{0.BAR}',
                foo='abc', BAR='def'
            ).result_backend,
            'abc:def'
        )

    def test_backend_custom_error(self):
        with self.assertRaises(ValueError) as context:
            Config(
                queues=[], result_backend='{0.foo}:{}',
                foo='abc'
            )
        self.assertEqual(
            getattr(context.exception, 'message', context.exception.args[0]),
            "Unable to render 'result_backend' value: '{0.foo}:{}'"
        )
