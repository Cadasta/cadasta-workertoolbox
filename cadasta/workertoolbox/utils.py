def extract_followups(task):
    """
    Retrieve callbacks and errbacks from provided task instance, disables
    tasks callbacks.
    """
    callbacks = task.request.callbacks
    errbacks = task.request.errbacks
    task.request.callbacks = None
    return {'link': callbacks, 'link_error': errbacks}
