# Cadasta Worker Toolbox

[![PyPI version](https://badge.fury.io/py/cadasta-workertoolbox.svg)](https://badge.fury.io/py/cadasta-workertoolbox)
[![Build Status](https://travis-ci.org/Cadasta/cadasta-workertoolbox.svg?branch=master)](https://travis-ci.org/Cadasta/cadasta-workertoolbox)
[![Requirements Status](https://requires.io/github/Cadasta/cadasta-workertoolbox/requirements.svg?branch=master)](https://requires.io/github/Cadasta/cadasta-workertoolbox/requirements/?branch=master)
<div align="center">
  <img width="250" src="https://user-images.githubusercontent.com/897290/27895378-a5bd9902-61cf-11e7-923e-fa07014bc5ed.png" alt="Worker Toolbox">
</div>

A collection of helpers to assist in quickly building asynchronous workers for the Cadasta system.


## Library


### `cadasta.workertoolbox.conf.Config`
The `Config` class was built to simplify configuring Celery settings, helping to ensure that all workers adhere to the architecture requirements of the Cadasta asynchronous system. It essentially offers a diff between Celery's default configuration and the configuration required by our system. It is the aim of the class to not require much customization on the part of the developer, however some customization may be needed when altering configuration between environments (e.g. if dev settings vary greatly from prod settings).

Any [Celery setting](http://docs.celeryproject.org/en/v4.0.2/userguide/configuration.html#new-lowercase-settings) may be submitted. It is internal convention that we use the Celery's newer lowercase settings rather than their older uppercase counterparts. This will ensure that they are displayed when calling `repr` on the `Conf` instance.

Once applied, all settings (and internal variables) are available on the Celery `app` instance's `app.conf` object.


#### Provided Configuration

Below is the configuration that the `Config` class will provide to a `Celery` instance.

##### `result_backend`
Defaults to `'db+postgresql://{0.RESULT_DB_USER}:{0.RESULT_DB_PASS}@{0.RESULT_DB_HOST}/{0.RESULT_DB_NAME}'` rendered with `self`.

##### `broker_transport`
Defaults to `'sqs`'.

##### `broker_transport_options`
Defaults to:

```python
{
    'region': 'us-west-2',
    'queue_name_prefix': '{}-'.format(QUEUE_NAME_PREFIX)
}
```

##### `task_queues`
Defaults to the following `set` of `kombu.Queue` objects, where `queues` is the configuration's internal `QUEUES` variable and `exchange` is a `kombu.Exchange` object constructed from the `task_default_exchange` and `task_default_exchange_type` settings:

```python
set([
    Queue('celery', exchange, routing_key='celery'),
    Queue(platform_queue, exchange, routing_key='#'),
] + [
    Queue(q_name, exchange, routing_key=q_name)
    for q_name in queues
])
```

_Note: It is recommended that developers not alter this setting._

##### `task_routes`
Defaults to a function that will generate a dict with the `routing_key` matching the value at the first index of a task name split on the `.` and the `exchange` set to a `kombu.Exchange` object constructed from the `task_default_exchange` and `task_default_exchange_type` settings

_Note: It is recommended that developers not alter this setting._

##### `task_default_exchange`
Defaults to `'task_exchange'`

##### `task_default_exchange_type`
Defaults to `'topic'`

##### `task_track_started`
Defaults to `True`.


#### Internal Variables
Below are arguments and environmental variables that can be used to customize the above provided configuration. By convention, all variables used to construct Celery configuration should should be written entirely uppercase. Unless otherwise stated, all variables may be specified via argument or environment variable (with preference given to argument).

##### `QUEUES` _(provided only via argument)_
This should contain an array of names for all service-related queues used by the Cadasta Platform. These values are used to construct the `task_queues` configuration. For the purposes of routing followup tasks, it's important that every task consumer is aware of all queues available. For this reason, if a queue is used by any service worker then it should be specified within this array. It is not necessary to include the `'celery'` or `'platform.fifo'` queues. Defaults to the contents of the `DEFAULT_QUEUES` variable in the modules [`__init__.py` file](/cadasta/workertoolbox/__init__.py).

##### `PLATFORM_QUEUE_NAME`
Defaults to `'platform.fifo'`.

_Note: It is recommended that developers not alter this setting._

##### `CHORD_UNLOCK_MAX_RETRIES`
Used to set the maximum number of times a `celery.chord_unlock` task may retry before giving up. See celery/celery#2725. Defaults to `43200` (meaning to give up after 6 hours, assuming the default of the task's `default_retry_delay` being set to 1 second).

##### `SETUP_LOGGING` _(provided only via argument)_
Controls whether a default logging configuration should be applied to the application. At a bare minimum, this includes:

* creating a console log handler for `INFO` level logs
* a file log handlers for `INFO` level logs, saved to `app.info.log`
* a file log handlers for `ERROR` level logs, saved to `app.error.log`

If the `OPBEAT_ORGANIZATION_ID` environment variable is set, the following logging configuration take place:

* add an [OpBeat](https://opbeat.com/) file handle for `ERROR` level logs
* add an [OpBeat](https://opbeat.com/) [task_failure signal](http://docs.celeryproject.org/en/latest/userguide/signals.html#task-failure) handler to log all faild tasks

Defaults to `True`.

##### `QUEUE_PREFIX`
Used to populate the `queue_name_prefix` value of the connections `broker_transport_options`. Defaults to value of `QUEUE_PREFIX` environment variable if populated, `'dev'` if not.

##### `RESULT_DB_USER`
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_USER` environment variable if populated, `'cadasta'` if not.

##### `RESULT_DB_PASS`
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_PASS` environment variable if populated, `'cadasta'` if not.

##### `RESULT_DB_HOST`
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_HOST` environment variable if populated, `'localhost'` if not.

##### `RESULT_DB_PORT`
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_PORT` environment variable if populated, `'cadasta'` if not.

##### `RESULT_DB_NAME`
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_NAME` environment variable if populated, `'5432'` if not.

### `cadasta.workertoolbox.setup.setup_app`
After the Celery application is provided a configuration object, there are other steups that must follow to properly configure the application. For example, the exchanges and queues described in the configuration must be declared. This function calls those required followup procedures. Typically, it is called automatically by the [`worker_init`](http://docs.celeryproject.org/en/latest/userguide/signals.html#worker-init) signal, however it must be called manually by codebases that are run only as task producers or from within a Python shell.

It takes two arguments:

* `app` - A `Celery()` app instance. _Required_
* `throw` - Boolean stipulating if errors should be raise on failed setup. Otherwise, errors will simply be logged to the module logger at `exception` level. _Optional, default: True_


### `cadasta.workertoolbox.tests.build_functional_tests`
When provided with a Celery app instance, this function generates a suite of functional tests to ensure that the provided application's configuration and functionality conforms with the architecture of the Cadasta asynchronous system.

An example, where an instanciated and configured `Celery()` app instance exists in a parallel `celery` module:

```python
from cadasta.workertoolbox.tests import build_functional_tests

from .celery import app

FunctionalTests = build_functional_tests(app)
```

To run these tests, use your standard test runner (e.g. `pytest`) or call manually from the command-line:

```bash
python -m unittest path/to/tests.py
```


## Contributing


### Testing

```bash
pip install -e .
pip install -r requirements-test.txt
./runtests
```


### Deploying

```bash
pip install -r requirements-deploy.txt
python setup.py test clean build tag publish
```
