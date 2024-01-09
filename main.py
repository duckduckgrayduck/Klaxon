"""
Uses BeautifulSoup to pull CSS selectors and prettify,
requests to pull content from archive.org and the webpage,
difflib to compare the archive and the current page,
uses re to pull the timestamp from the archive result,
savepagenow to archive pages that are updated.
"""
import difflib
import os
import re
import sys
import requests
from pathlib import Path
import savepagenow
from documentcloud.addon import AddOn
from documentcloud.toolbox import requests_retry_session
from bs4 import BeautifulSoup


class Klaxon(AddOn):
    """Add-On that will monitor a site for changes and alert you for updates"""

    def check_first_seen(self, site):
        """Checks to see if this site has ever been archived on Wayback"""
        archive_test = f"https://archive.org/wayback/available?url={site}"
        print(archive_test)
        headers = {'User-Agent': 'Klaxon https://github.com/MuckRock/Klaxon'}
        response = requests_retry_session(retries=10).get(archive_test, headers=headers)
        print(response)
        try:
            resp_json = response.json()
        except requests.exceptions.JSONDecodeError as j:
            sys.exit(0)
        print(resp_json)
        if resp_json["archived_snapshots"] == {} and self.site_data == {}:
            first_seen_url = savepagenow.capture(site, authenticate=True)
            subject = "Klaxon Alert: New Site Archived"
            message = (
                f"{site} has never been archived "
                "using the Wayback Machine until now.\n"
                f"The first snapshot is now available here: {first_seen_url} \n"
                "We will alert you if changes are made during the next run."
            )
            self.send_notification(subject, message)
            timestamp = self.get_timestamp(first_seen_url)
            self.site_data["timestamp"] = timestamp
            print(self.site_data)
            self.store_event_data(self.site_data)
            sys.exit(0)
        if resp_json["archived_snapshots"] != {} and self.site_data == {}:
            self.site_data["timestamp"] = resp_json["archived_snapshots"]["closest"]["timestamp"]
            self.store_event_data(self.site_data)
            print(self.site_data)

    def send_notification(self, subject, message):
        """Send notifications via slack and email"""
        self.send_mail(subject, message)
        if self.data.get("slack_webhook"):
            requests_retry_session().post(
                self.data.get("slack_webhook"), json={"text": f"{subject}\n\n{message}"}
            )

    def get_timestamp(self, url):
        """Gets a timestamp from an archive.org URL"""
        res = re.search("\d{14}", url)
        if res is None:
            self.send_mail(
                "Klaxon Runtime Error",
                "Regex failed to find a timestamp "
                f"for url {url}. \n Please forward this email to info@documentcloud.org",
            )
            sys.exit(1)
        return res.group()

    def get_elements(self, site, selector):
        """Given a URL and css selector, pulls the elements using BeautifulSoup"""
        headers = {'User-Agent': 'Klaxon https://github.com/MuckRock/Klaxon'}
        html = requests_retry_session(retries=10).get(site, headers=headers)
        soup = BeautifulSoup(html.text, "html.parser")
        elements = soup.select(selector)
        return elements

    def get_wayback_url(self, site):
        """Given a site, returns the most recent wayback url containing original html
        If this is the first time running the Add-On, gets all the wayback entries for the URL
        & pulls the most recent entry's timestamp. Else gets the last timestamp from event data.
        """
        if self.site_data == {}:
            headers = {'User-Agent': 'Klaxon https://github.com/MuckRock/Klaxon'}
            response = requests_retry_session(retries=10).get(
                f"http://web.archive.org/cdx/search/cdx?url={site}", 
                headers=headers
            )
            # Filter only for the successful entries
            successful_saves = [
                line for line in response.text.splitlines() if line.split()[4] == "200"
            ]
            # Get the last successful entry & timestamp for that entry
            last_save = successful_saves[-1]
            timestamp = self.get_timestamp(last_save)
            self.timestamp1 = timestamp
            # Generate the URL for the last successful save's raw HTML file
            full_url = f"https://web.archive.org/web/{timestamp}id_/{site}"
        else:
            # Gets the last seen timestamp from event data, must be a scheduled Add-On run.
            timestamp = self.site_data["timestamp"]
            self.timestamp1 = timestamp
            full_url = f"https://web.archive.org/web/{timestamp}id_/{site}"
        return full_url

    def get_changes_url(self, site, timestamp1, timestamp2):
        """Generates a wayback changes URL given a site and two timestamps"""
        return f"https://web.archive.org/web/diff/{timestamp1}/{timestamp2}/{site}"

    def monitor_with_selector(self, site, selector):
        """Monitors a particular site for changes and sends a diff via email"""
        # Accesses the workflow secrets to run Wayback save's with authentication
        os.environ["SAVEPAGENOW_ACCESS_KEY"] = os.environ["KEY"]
        os.environ["SAVEPAGENOW_SECRET_KEY"] = os.environ["TOKEN"]

        self.check_first_seen(site)
        archive_url = self.get_wayback_url(site)

        # Grab the elements for the archived page and the current site
        old_elements = self.get_elements(archive_url, selector)
        new_elements = self.get_elements(site, selector)

        # If there are no changes detected, you do not get a notification.
        if old_elements == new_elements:
            sys.exit(0)
        else:
            # Generates a list of strings using prettify to pass to difflib
            old_tags = [x.prettify() for x in old_elements]
            new_tags = [y.prettify() for y in new_elements]

            # Generates HTML view that shows diffs in a pretty format
            html_diff = difflib.HtmlDiff().make_file(old_tags, new_tags, context=True)
            # Saves the view as a file
            Path("diff.html").write_text(html_diff)

            # Uploads the file to S3, grabs the file, and emails it to the user.
            self.upload_file(open("diff.html"))
            resp = self.client.get(f"addon_runs/{self.id}/")
            file_url = resp.json()["file_url"]

            # Captures the current version of the site in Wayback.
            try:
                new_archive_url = savepagenow.capture(site, authenticate=True)
                new_timestamp = self.get_timestamp(new_archive_url)
                self.site_data["timestamp"] = new_timestamp
                self.store_event_data(self.site_data)
                old_timestamp = self.timestamp1
                changes_url = self.get_changes_url(site, old_timestamp, new_timestamp)
                # rare edge case where Wayback savepagenow returns the old archive URL
                # usually when a site is archived in rapid succession.
                if new_timestamp == old_timestamp:
                    sys.exit(0)
            except savepagenow.exceptions.WaybackRuntimeError as e:
                sys.exit(0)
            except savepagenow.exceptions.CachedPage as c:
                sys.exit(0)
            self.send_notification(
                f"Klaxon Alert: {site} Updated",
                f"Get results here (you must be logged in!): {file_url} \n"
                f"New snapshot: {new_archive_url} \n"
                f"Visual content wayback comparison: {changes_url}",
            )

    def main(self):
        """Gets the site and selector from the Add-On run, checks  calls monitor"""
        # Gets the site and selector from the front-end yaml
        site = self.data.get("site")
        print(site)
        selector = self.data.get("selector")
        # Loads event data, only will be populated if a scheduled Add-On run.
        self.site_data = self.load_event_data()
        print(self.site_data)
        if self.site_data is None:
            self.site_data = {}
        self.set_message("Checking the site for updates...")
        self.monitor_with_selector(site, selector)
        self.set_message("Detection complete")


if __name__ == "__main__":
    Klaxon().main()
