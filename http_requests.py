import time
import logging

logging.basicConfig(filename="example.log", level=logging.DEBUG)


def prevent_429(func, **kwargs):
    """Handles outside requests and waits if there's an error"""
    try:
        return func(**kwargs)
    except Exception as e:

        print(e)
        print(f"Error in {func.__name__}")

        logging.warning(
            f"{func.__name__} failed with {e} with this request body: {kwargs}",
            exc_info=True,
        )
        return None
