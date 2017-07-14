from celery import Celery

from cadasta.workertoolbox.conf import Config
from cadasta.workertoolbox.tests import build_functional_tests


app = Celery()
conf = Config(queues=('exports',))
app.config_from_object(conf)
FunctionalTests = build_functional_tests(app)
