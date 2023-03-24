"""
Uses BeautifulSoup to pull CSS selectors and prettify,
requests to pull content from archive.org and the webpage,
difflib to compare the archive and the current page,
uses re to pull the timestamp from the archive result,
savepagenow to archive pages that are updated.
"""
import difflib
import re
import sys
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
        response = requests_retry_session(retries=8).get(archive_test)
        resp_json = response.json()
        if resp_json["archived_snapshots"] == {}:
            savepagenow.capture(site)
            self.send_mail(
                "Klaxon Alert: New Site Archived",
                f"The site you provided: {site} has never been archived \
                using the Wayback Machine until now. \
                We will alert you if changes are made during the next run.",
            )
            sys.exit(0)

    def get_elements(self, site, selector):
        """Given a URL and css selector, pulls the elements using BeautifulSoup"""
        html = requests_retry_session(retries=8).get(site)
        soup = BeautifulSoup(html.text, "html.parser")
        elements = soup.select(selector)
        return elements

    def get_wayback_url(self, site):
        """Given a site, returns the most recent wayback entry url containing original html"""
        # Get the full list of archive.org entries
        response = requests_retry_session(retries=8).get(
            f"http://web.archive.org/cdx/search/cdx?url={site}"
        )
        # Filter only for the successful entries
        successful_saves = [
            line for line in response.text.splitlines() if line.split()[4] == "200"
        ]
        # Get the last successful entry & timestamp for that entry
        last_save = successful_saves[-1]
        res = re.search("\d{14}", last_save)
        timestamp = res.group()
        # Generate the URL for the last successful save's raw HTML file
        full_url = f"https://web.archive.org/web/{timestamp}id_/{site}"
        return full_url

    def monitor_with_selector(self, site, selector):
        """Monitors a particular site for changes and sends a diff via email"""
        self.check_first_seen(site)
        archive_url = self.get_wayback_url(site)

        # Grab the elements for the archived page and the current site
        old_elements = self.get_elements(archive_url, selector)
        new_elements = self.get_elements(site, selector)

        if old_elements == new_elements:
            self.set_message("No changes in page since last archive")
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
            self.send_mail(
                "Klaxon Alert: Site Updated", f"Get results here: {file_url}"
            )

            # Captures the current version of the site in Wayback.
            savepagenow.capture(site)

    def main(self):
        """Gets the site and selector from the Add-On run, calls monitor"""
        site = self.data.get("site")
        selector = self.data.get("selector")
        self.monitor_with_selector(site, selector)


if __name__ == "__main__":
    Klaxon().main()
