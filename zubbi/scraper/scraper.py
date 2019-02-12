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

import hashlib
import logging

from zubbi.doc import render_sphinx, SphinxBuildError
from zubbi.models import ZuulJob
from zubbi.scraper.connections.zuul import ZuulApi
from zubbi.scraper.exceptions import CheckoutError


LOGGER = logging.getLogger(__name__)

ZUUL_DIRECTORIES = ["zuul.d", ".zuul.d"]

ZUUL_FILES = ["zuul.yaml", ".zuul.yaml"]

README_FILES = ["README.rst", "README.md", "README.txt", "README"]

CHANGELOG_FILES = ["CHANGELOG.rst", "CHANGELOG.md", "CHANGELOG.txt", "CHANGELOG"]

REPO_ROOT = "/"


class Scraper:
    def __init__(self, repo):
        self.repo = repo

    def scrape(self):
        LOGGER.info("Scraping '%s'", self.repo.repo_name)

        job_files = self.check_out_job_files()
        role_files = self.check_out_role_files()

        return job_files, role_files

    def check_out_job_files(self):
        job_files = {}

        root_files = self.repo.list_directory(REPO_ROOT)

        # Search zuul directories
        for directory in ZUUL_DIRECTORIES:
            # Skip non-existing zuul dirs
            if directory not in root_files.keys():
                continue
            try:
                remote_files = self.repo.list_directory(directory)
                for filename, file_content in remote_files.items():
                    rel_path = file_content.path
                    try:
                        job_files[rel_path] = {
                            "last_changed": self.repo.last_changed(rel_path),
                            "blame": self.repo.blame(rel_path),
                            "content": self.repo.check_out_file(rel_path),
                        }
                    except CheckoutError as e:
                        LOGGER.exception(e)
            except CheckoutError as e:
                LOGGER.debug(e)

        # Search zuul files
        for zuul_file in ZUUL_FILES:
            # Skip non-existing zuul files
            if zuul_file not in root_files.keys():
                continue
            try:
                job_files[zuul_file] = {
                    "last_changed": self.repo.last_changed(zuul_file),
                    "blame": self.repo.blame(zuul_file),
                    "content": self.repo.check_out_file(zuul_file),
                }
            except CheckoutError as e:
                LOGGER.debug(e)

        return job_files

    def check_out_role_files(self):
        role_files = {}
        # Try to access the 'roles' directory
        try:
            roles = self.repo.list_directory("roles")
            for role_name, role_content in roles.items():
                try:
                    last_changed = self.repo.last_changed(role_content.path)
                    existing_files = self.repo.list_directory(role_content.path)
                    # Skip empty directories or files
                    if not existing_files:
                        continue
                    readme_file = self.find_matching_file(README_FILES, existing_files)
                    changelog_file = self.find_matching_file(
                        CHANGELOG_FILES, existing_files
                    )
                    role_files[role_name] = {
                        "last_changed": last_changed,
                        "readme_file": readme_file,
                        "changelog_file": changelog_file,
                    }
                except CheckoutError as e:
                    LOGGER.exception(e)
        except CheckoutError as e:
            LOGGER.debug(e)

        return role_files

    def find_matching_file(self, file_filter, existing_files):
        for filename, file_content in existing_files.items():
            if filename not in file_filter:
                continue
            try:
                rel_path = file_content.path
                # Return the first matching file
                match = {
                    "path": rel_path,
                    "content": self.repo.check_out_file(rel_path),
                }
                return match
            except CheckoutError as e:
                LOGGER.exception(e)


class TenantScraper:
    def __init__(self, tenant, zuul_con, scrape_time):
        self.tenant = tenant
        self.zuul_api = ZuulApi(zuul_con)
        self.scrape_time = scrape_time

    def scrape(self):
        tenant_jobs = self.zuul_api.get_jobs(self.tenant)
        if not tenant_jobs:
            LOGGER.warning("No job list to parse for tenant '%s'", self.tenant)
            return
        LOGGER.info(
            "Found %d job definitions for tenant '%s", len(tenant_jobs), self.tenant
        )
        job_definitions = self.parse_job_definitions(tenant_jobs)
        return job_definitions

    def parse_job_definitions(self, tenant_jobs):
        LOGGER.info("Parsing job definitions for tenant '%s", self.tenant)
        job_definitions = []
        for job_name, jobs in tenant_jobs.items():
            # How to deal with this job-list?
            for job in jobs:
                repo = None
                source_context = job.get("source_context")
                if source_context:
                    repo = job.get("source_context", {}).get("project")
                uuid = hashlib.sha1(
                    str.encode("{}{}".format(repo, job_name))
                ).hexdigest()
                zuul_job = ZuulJob(meta={"id": uuid})
                zuul_job.job_name = job_name
                zuul_job.repo = repo
                zuul_job.tenants = [self.tenant]
                zuul_job.private = False
                zuul_job.scrape_time = self.scrape_time
                # TODO line_start and line_end
                # TODO last_updated
                # TODO url
                zuul_job.description = job["description"]
                try:
                    doc = render_sphinx(zuul_job.description)
                    zuul_job.description_html = doc["html"]
                    zuul_job.platforms = doc["platforms"]
                    # TODO Get .. include:: files for Sphinx
                except SphinxBuildError as exc:
                    LOGGER.warning(
                        "Description of job '%s' could not be " "converted to HTML: %s",
                        job_name,
                        exc,
                    )

                zuul_job.parent = job["parent"]

                job_definitions.append(zuul_job)
        return job_definitions
