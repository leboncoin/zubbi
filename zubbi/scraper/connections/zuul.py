# Copyright 2018 BMW Car IT GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
from json.decoder import JSONDecodeError

import requests

from zubbi.utils import urljoin


LOGGER = logging.getLogger(__name__)


class ZuulConnection:
    def __init__(self, url):
        self.url = url
        self._session = None

    def init(self):
        LOGGER.info("Initializing Zuul connection to %s", self.url)

    @property
    def provider(self):
        return "zuul"

    @property
    def session(self):
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def get(self, endpoint):
        endpoint_url = urljoin(self.url, endpoint)
        request = requests.Request("GET", endpoint_url)
        prep_request = self.session.prepare_request(request)
        response = self.session.send(prep_request)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            LOGGER.error("API request to %s failed: %s", endpoint_url, str(exc))
            response = None
        return response


class ZuulApi:
    def __init__(self, zuul_con):
        self.con = zuul_con

    def get_jobs(self, tenant):
        endpoint = "api/tenant/{}/jobs?full=true".format(tenant)
        response = self.con.get(endpoint)
        if not response:
            LOGGER.error("Could not retrieve job list for tenant '%s'", tenant)
            return
        try:
            json_response = response.json()
            return json_response
        except JSONDecodeError:
            LOGGER.error(
                "Job list for tenant '%s' could not be parsed as JSON.", tenant
            )

    def get_job(self, tenant, job_name):
        endpoint = "api/tenant/{}/job/{}".format(tenant, job_name)
        result = self.con.get(endpoint)
        return result

    def search_jobs(self, query, exact, start, end):
        # TODO (felix): Add list of fields that should be searched for the query_string
        # TODO (felix): Find a better way to provide the parameters (based on requests?)
        endpoint = "api/search_jobs?query={}&start={}&end={}&exact={}".format(
            query, start, end, exact
        )
        result = self.con.get(endpoint)
        return result
