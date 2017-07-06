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
