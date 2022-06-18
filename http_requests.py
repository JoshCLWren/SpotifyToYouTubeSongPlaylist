import time
import logging
import arrow
import json
import os
import youtube_request

logging.basicConfig(filename=f"{arrow.now().format('YYYY-MM-DD')}-errors.log", level=logging.DEBUG)


def handle_request(func, time_to_wait=1, time_waited=0, **kwargs):
    """Handles outside requests and waits if there's an error"""
    time_waited = time_waited + time_to_wait
    try:
        time.sleep(time_to_wait)
        call = func(**kwargs)
        logging.warning(f"{arrow.now().isoformat()}{time_waited} seconds waited, no error, for {func.__name__}")
        return call
    except Exception as e:
        if isinstance(e, AttributeError):
            logging.warning(f"AttributeError: {e}")
        if e.status_code == 403 and func.__name__ == "execute":
            return None
        if e.status_code == 401 and func.__name__ == "execute":
            youtube_auth = youtube_request.YouTubeAuthSession()
            youtube_auth.new()
            return func(**kwargs)
        if e.status_code not in [*range(200, 300)]:
            time_to_wait *= 2
            time_waited += time_to_wait
            time.sleep(time_to_wait)
            log = f"{arrow.now().isoformat()} {time_waited} seconds waited, error, for {func.__name__}, trying again in {time_to_wait} seconds "
            print(log)
            logging.warning(log, exc_info=True)
            return handle_request(func, time_waited=time_waited, time_to_wait=time_to_wait, **kwargs)

        print(e)
        print(f"Error in {func.__repr__}, waiting {time_waited} seconds, kwargs: {kwargs}")

        logging.warning(
            f"{arrow.now().isoformat()}{func.__name__} failed with {e} with this request body: {kwargs}",
            exc_info=True,
        )
        return None
