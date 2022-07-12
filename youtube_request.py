"""module for making requests to YouTube api"""

import json
import os
import pickle

import aiofiles
import arrow
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import requests


class Quota:
    """A class with quota related state properties"""

    def __init__(
        self,
    ):
        self.daily_quota = 10000
        self.remaining = 10000
        # quota resets at midnight pacific time
        self.today = arrow.now("US/Pacific").format("YYYY-MM-DD")
        self.resets_at_time = arrow.get(f"{self.today}T00:00:00-08:00")
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_requests = self.successful_requests + self.failed_requests

    def spend(self, amount):
        """Uses the quota"""
        self.remaining -= amount
        return self.remaining

    def check(self):
        """Gets the quota"""
        return self.remaining

    def reset(self):
        """Resets the quota"""
        self.remaining = self.daily_quota
        return self.remaining

    def budget(self, amount):
        """Budget the quota"""
        return self.remaining >= amount

    def log_success(self, response, obj):
        """Logs a successful request"""

        if not os.path.exists("quota_log.json"):
            with open("quota_log.json", "w") as f:
                json.dump({"data": []}, f)
        with open("quota_log.json", "r") as f:
            cache = json.load(f)

        cache["data"].append(
            {
                f"{arrow.now()}": {
                    "request": response,
                    "obj": obj,
                    "success": True,
                    "quota": self.remaining,
                    "total": self.total_requests,
                }
            }
        )

        with open("./quota_log.json", "w") as f:
            json.dump(cache, f)
        self.successful_requests += 1
        self.total_requests += 1


#
# class YouTubeRequest:
#     """A class with YouTube request related state properties"""
#
#     def __init__(self, quota, youtubeauth_session):
#         self.quota = quota
#         self.base_url = "https://www.googleapis.com/youtube/v3/"
#         self.api_key = os.environ.get("YOUTUBE_API_KEY")
#         self.headers = {
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {self.api_key}",
#         }
#         self.session = youtubeauth_session
#
#     def execute(self, endpoint, **kwargs):
#         """Executes a request"""
#         if self.quota.budget(1):
#             self.quota.spend(1)
#             return self.request(endpoint, **kwargs)
#         else:
#             return None
#
#     def request(self):
#         return googleapiclient.discovery.build(
#             "youtube", "v3", credentials=self.session
#         )


class YouTubeAuthSession:
    """A class with YouTube auth session related state properties"""

    def __init__(self):
        self.auth_status = False
        self.scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.client_secrets_file = "client_secret_YouTube.json"
        self.credentials = self.get_creds()
        self.discovery = googleapiclient.discovery.build(
            "youtube", "v3", credentials=self.credentials
        )

    def get_creds(self):
        """initialize and authenticate with Youtube"""
        # Get credentials and create an API client
        # check if the cache is recent enough to use
        if os.path.exists("token.pickle"):
            with open("token.pickle", "rb") as token:
                creds = pickle.load(token)
        if creds.valid and creds.expired is False:
            return creds
        port = os.environ.get("PORT", 8080)
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            self.client_secrets_file, self.scopes
        )
        try:
            creds = flow.run_local_server(port=port)
        except OSError:
            port = int(port) + 1
            print(f"The server is still running, trying port {port}")

            creds = flow.run_local_server(port=port)
        # if there are credentials, save them to the token.pickle file
        with open("token.pickle", "wb") as token:

            pickle.dump(creds, token)

        return creds
