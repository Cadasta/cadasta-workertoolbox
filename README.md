# Cadasta Worker Toolbox

[![PyPI version](https://badge.fury.io/py/cadasta-workertoolbox.svg)](https://badge.fury.io/py/cadasta-workertoolbox)
[![Build Status](https://travis-ci.org/Cadasta/cadasta-workertoolbox.svg?branch=master)](https://travis-ci.org/Cadasta/cadasta-workertoolbox)
[![Requirements Status](https://requires.io/github/Cadasta/cadasta-workertoolbox/requirements.svg?branch=master)](https://requires.io/github/Cadasta/cadasta-workertoolbox/requirements/?branch=master)
<div align="center">
  <img width="250" src="https://user-images.githubusercontent.com/897290/27895378-a5bd9902-61cf-11e7-923e-fa07014bc5ed.png" alt="Worker Toolbox">
</div>

A collection of helpers to assist in quickly building asynchronous workers for the Cadasta system.

## Architecture

![Async System Architecture Diagram](https://user-images.githubusercontent.com/897290/28102799-e9b04182-668e-11e7-84ae-51c6fa307303.png "Async System Architecture Diagram")

The Cadasta asynchronous system is designed so that both the scheduled tasks and the task results can be tracked by the central [Cadasta Platform](https://github.com/Cadasta/cadasta-platform). To ensure that this takes place, all Celery workers must be correctly configured to support these features.

### Tracking Scheduled Tasks
To keep our system aware of all tasks being scheduled, the Cadasta Platform has a process running to consume task messages off of a task-monitor queue and insert those messages into our database. To support this design, all task producers (including worker nodes) must publish their task messages to both the normal destination queues and the task-monitor queue. This is acheived by registering all queues with a [Topic Exchange](http://docs.celeryproject.org/en/latest/userguide/routing.html#topic-exchanges), setting the task-monitor queue to subscribe to all messages sent to the exchange, and setting standard work queues to subscribe to messages with a matching `routing_key`. Being that the Cadasta Platform is designed to work with Amazon SQS and the [SQS backend only keeps exchange/queue declarations in memory](http://docs.celeryproject.org/projects/kombu/en/v4.0.2/introduction.html#f1), each message producer must have this set up within their configuration. (For more reading on Exchanges, see the [RabbitMQ Tutorials 1-5](https://www.rabbitmq.com/tutorials/tutorial-one-python.html))

### Tracking Task Results

Tasks results are inserted by each worker into the Platform DB. For this reason, it is important that each worker have network access to the Platform DB (via AWS Security Groups). Additionally, each worker should have a provided username and password that grants them authorization to write to the Platform DB's Result Table. For reasons of security, it is advised that these credentials be permitted to only access this single table. The Result Table has a one-to-one relation via the `task_id` column to the Task Table. This should not be enforced via a constraint, as it is possible for a task's result to be entered into the DB _before_ the sync-tasks service enters the task into the Task Table.


## Library

### `cadasta.workertoolbox.conf.Config`
The `Config` class was built to simplify configuring Celery settings, helping to ensure that all workers adhere to the architecture requirements of the Cadasta asynchronous system. It essentially offers a diff between Celery's default configuration and the configuration required by our system. It is the aim of the class to not require much customization on the part of the developer, however some customization may be needed when altering configuration between environments (e.g. if dev settings vary greatly from prod settings).

Any [Celery setting](http://docs.celeryproject.org/en/v4.0.2/userguide/configuration.html#new-lowercase-settings) may be submitted. It is internal convention that we use the Celery's newer lowercase settings rather than their older uppercase counterparts. This will ensure that they are displayed when calling `repr` on the `Conf` instance.

Once applied, all settings (and internal variables) are available on the Celery `app` instance's `app.conf` object.

#### Provided Configuration

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
By convention, all variables used to construct Celery configuration should should be written entirely uppercase.

##### `QUEUES`
This should contain an array of names for all service-related queues used by the Cadasta Platform. These values are used to construct the `task_queues` configuration. For the purposes of routing followup tasks, it's important that every task consumer is aware of all queues available. For this reason, if a queue is used by any service worker then it should be specified within this array. It is not necessary to include the `'celery'` or `'platform.fifo'` queues. Defaults to the contents of the `DEFAULT_QUEUES` variable in the modules [`__init__.py` file](/cadasta/workertoolbox/__init__.py).

##### `PLATFORM_QUEUE_NAME`
Defaults to `'platform.fifo'`.

_Note: It is recommended that developers not alter this setting._

##### `QUEUE_NAME_PREFIX`
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
Used to populate the default `result_backend` template. Defaults to `RESULT_DB_PORT` environment variable if populated, `'5432'` if not.

##### `CHORD_UNLOCK_MAX_RETRIES`
Used to set the maximum number of times a `celery.chord_unlock` task may retry before giving up. See celery/celery#2725. Defaults to `43200` (meaning to give up after 6 hours, assuming the default of the task's `default_retry_delay` being set to 1 second).

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

## Developing Workers with Worker Toolbox

### Celery Best Practices and Gotchas

- To make the most of task performance, take advantage of [Celery's Canvas functionality](http://docs.celeryproject.org/en/latest/userguide/canvas.html).
- [Avoid launching synchronous subtasks.](http://docs.celeryproject.org/en/latest/userguide/tasks.html?highlight=granularity#avoid-launching-synchronous-subtasks)
- [Pursue granularity.](http://docs.celeryproject.org/en/latest/userguide/tasks.html?highlight=granularity#granularity) when writing tasks.
- If your task schedules other tasks (eg a `chain` or `chord`), it is important to pass the parent task's callbacks/errbacks to the last task of the subtasks. (TODO: Add helper function)
- At time of writing, chords with single tasks don't respect callbacks/errbacks (celery/celery#3317, celery/celery#3709, celery/celery#3597).

### Common Issues

#### `celery.exceptions.NotRegistered: '...'`

```python
[2017-08-09 10:49:23,338: ERROR/MainProcess] Pool callback raised exception: Task of kind 'msg.email_err' never registered, please make sure it's imported.
Traceback (most recent call last):
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/kombu/utils/objects.py", line 42, in __get__
    return obj.__dict__[self.__name__]
KeyError: 'type'

During handling of the above exception, another exception occurred:

Traceback (most recent call last):
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/billiard/pool.py", line 1747, in safe_apply_callback
    fun(*args, **kwargs)
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/celery/worker/request.py", line 366, in on_failure
    self.id, exc, request=self, store_result=self.store_errors,
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/celery/backends/base.py", line 168, in mark_as_failure
    self._call_task_errbacks(request, exc, traceback)
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/celery/backends/base.py", line 174, in _call_task_errbacks
    if arity_greater(errback.type.__header__, 1):
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/kombu/utils/objects.py", line 44, in __get__
    value = obj.__dict__[self.__name__] = self.__get(obj)
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/celery/canvas.py", line 490, in type
    return self._type or self.app.tasks[self['task']]
  File "/Users/alukach/.virtualenvs/export-worker/lib/python3.6/site-packages/celery/app/registry.py", line 19, in __missing__
    raise self.NotRegistered(key)
celery.exceptions.NotRegistered: 'msg.email_err'
```

This occurs when a task experiences an exception and has an errback/link_error. For whatever reason, it attempts to run the task right then and there (as opposed to scheduling it in the queues). This is problematic if the errback is for a task not available in the worker's codebase. For whatever reason, this does not seem to occur in tasks that are run within a `chord`. See celery/kombu#4022.

## Contributing

### Testing

```bash
pip install -r requirements-test.txt
./runtests
```

### Deploying

```bash
pip install -r requirements-deploy.txt
python setup.py test clean build tag publish
```
