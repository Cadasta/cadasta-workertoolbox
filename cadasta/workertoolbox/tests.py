import unittest
from mock import patch, MagicMock


def build_functional_tests(app, is_worker=True):
    """
    Helper to produce sanity tests for provided configuration.

    app: A configured Celery app instance
    is_worker: If this codebase is to be run as a Celery worker (as
        opposed to a codebase that is only a task producer).
    """
    class TestConfigFunctional(unittest.TestCase):
        """ Ensure that our configuration provides expected functionality """

        @classmethod
        @patch('kombu.transport.SQS.Channel.sqs', MagicMock())
        def setUpClass(cls):
            cls.app = app
            if is_worker:
                app.Worker()  # Init worker (sends signal)
            cls.channel = cls.app.connection().channel()

        def test_default_queue_name(self):
            """ Ensure default queue is correctly named """
            self.assertEqual(
                self.app.conf.task_default_queue, 'celery')

        def test_platform_queue_name(self):
            """ Ensure platform queue is correctly named """
            self.assertEqual(
                self.app.conf.PLATFORM_QUEUE_NAME, 'platform.fifo')

        def test_default_exchange_type(self):
            """ Ensure default exchange is topic exchange """
            def_exch = self.app.conf.task_default_exchange
            exch_type = self.channel.typeof(def_exch).type
            self.assertEqual(exch_type, 'topic')

        def test_default_exchange_routing(self):
            """ Ensure default exchange routes tasks to multiple queues """
            exchange = self.app.conf.task_default_exchange
            for q in self.app.conf.QUEUES:
                queues = self.channel.typeof(exchange).lookup(
                    table=self.channel.get_table(exchange),
                    exchange=exchange, routing_key=q,
                    default=self.app.conf.task_default_queue)
                self.assertEqual(len(queues), 2)
                self.assertTrue(q in queues)
                self.assertTrue(self.app.conf.PLATFORM_QUEUE_NAME in queues)

        def test_celery_exchange_routing(self):
            """
            Ensure celery queue and platform queue are registered with default
            exchange
            """
            exchange = self.app.conf.task_default_exchange
            queues = self.channel.typeof(exchange).lookup(
                table=self.channel.get_table(exchange),
                exchange=exchange, routing_key='celery',
                default=self.app.conf.task_default_queue)

            self.assertEqual(len(queues), 2)
            self.assertTrue('celery' in queues)
            self.assertTrue(self.app.conf.PLATFORM_QUEUE_NAME in queues)

        def test_celery_task_routing(self):
            """
            Ensure celery tasks route to celery queue and platform queue
            """
            options = self.app.amqp.router.route({}, 'celery.chord_unlock')
            self.assertNotIn('queue', options)
            self.assertIn('exchange', options)
            self.assertIn('routing_key', options)
            exchange = options['exchange'].name
            routing_key = options['routing_key']

            queues = self.channel.typeof(exchange).lookup(
                table=self.channel.get_table(exchange),
                exchange=exchange, routing_key=routing_key,
                default=self.app.conf.task_default_queue)
            self.assertEqual(len(queues), 2)
            self.assertTrue('celery' in queues)
            self.assertTrue(self.app.conf.PLATFORM_QUEUE_NAME in queues)

        def test_max_retries(self):
            """ Ensure that, by default, max_retries is set to an int """
            self.assertEqual(
                type(self.app.tasks['celery.chord_unlock'].max_retries),
                int)

    return TestConfigFunctional
