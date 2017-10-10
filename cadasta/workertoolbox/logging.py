from celery.utils.log import ColorFormatter as ColorFormatterBase


class ColorFormatter(ColorFormatterBase):
    def __init__(self, fmt, use_color=True, *args, **kwargs):
        super(ColorFormatter, self).__init__(fmt, use_color)
