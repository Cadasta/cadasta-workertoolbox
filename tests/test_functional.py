from celery import Celery, signals

from cadasta.workertoolbox.conf import Config
from cadasta.workertoolbox.tests import build_functional_tests


app = Celery()
conf = Config(imports=tuple())
app.config_from_object(conf)


class FunctionalTests(build_functional_tests(app)):

    def test_set_chord_unlock_retry_limit(self):
        """
        Ensure that CHORD_UNLOCK_MAX_RETRIES are applied when worker
        signal is sent.
        """
        my_app = Celery()
        my_app.config_from_object(Config(CHORD_UNLOCK_MAX_RETRIES=1234))

        self.assertEqual(my_app.tasks['celery.chord_unlock'].max_retries, None)

        class sender():
            app = my_app

        signals.worker_init.send(sender=sender)
        self.assertEqual(my_app.tasks['celery.chord_unlock'].max_retries, 1234)
