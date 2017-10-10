from celery.utils.log import ColorFormatter as ColorFormatterBase


def extract_followups(task):
    """
    Retrieve callbacks and errbacks from provided task instance, disables
    tasks callbacks.
    """
    callbacks = task.request.callbacks
    errbacks = task.request.errbacks
    task.request.callbacks = None
    return {'link': callbacks, 'link_error': errbacks}


class ColorFormatter(ColorFormatterBase):
    def __init__(self, fmt, use_color=True, *args, **kwargs):
        super(ColorFormatter, self).__init__(fmt, use_color)
