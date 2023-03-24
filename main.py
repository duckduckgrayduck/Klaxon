"""
Uses BeautifulSoup to pull CSS selectors and prettify,
requests to pull content from archive.org and the webpage,
difflib to compare the archive and the current page,
uses re to pull the timestamp from the archive result,
savepagenow to archive pages that are updated.
"""
from documentcloud.addon import AddOn
from bs4 import BeautifulSoup
from pathlib import Path
import requests
import re 
import sys
import difflib as dl
import savepagenow

class Klaxon(AddOn):
    """Add-On that will monitor a site for changes and alert you for updates"""
    
    def get_elements(self, site, selector):
        html = requests.get(site)
        soup = BeautifulSoup(html.text, 'html.parser')
        elements = soup.select(selector)
        return elements

    def get_wayback_url(self,site):
        # Get the full list of archive.org entries
        response = requests.get(f'http://web.archive.org/cdx/search/cdx?url={site}')
        # Filter only for the successful entries
        successful_saves = [
            line for line in response.text.splitlines()
            if line.split()[4] == "200"
        ] 
        # Get the last successful entry & timestamp for that entry
        last_save = successful_saves[-1]
        r = re.search("\d{14}", last_save)
        timestamp = r.group()
        # Generate the URL for the last successful save's raw HTML file
        full_url = f'https://web.archive.org/web/{timestamp}id_/{site}'
        return full_url

    def monitor_with_selector(self, site, selector):
        """ Monitors a particular site for changes and sends a diff via email """
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
            html_diff = dl.HtmlDiff().make_file(old_tags, new_tags, context=True)
            # Saves the view as a file
            Path('diff.html').write_text(html_diff)

            # Uploads the file to S3, grabs the file, and emails it to the user. 
            self.upload_file(open("diff.html"))
            resp = self.client.get(f"addon_runs/{self.id}/")
            file_url = resp.json()["file_url"]
            self.send_mail("Klaxon Alert: Site Updated", f"Get results here: {file_url}")
    
            # Captures the current version of the site in Wayback. 
            savepagenow.capture(site)

    def main(self):
        site = self.data.get("site")
        selector = self.data.get("selector")
        self.monitor_with_selector(site, selector)

if __name__ == "__main__":
    Klaxon().main()
