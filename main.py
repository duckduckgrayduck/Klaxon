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
import difflib as dl
import savepagenow

class Klaxon(AddOn):
    """Add-On that will monitor a site for changes and alert you for updates"""
    def monitor_with_selector(self, site, selector):
        # Get the full list of archive.org entries
        response = requests.get(f'http://web.archive.org/cdx/search/cdx?url={site}')
        # Filter only for the successful entries
        successful_saves = []
        for line in response.text.splitlines():
            if ' 200 ' in line:
                successful_saves.append(line)
        # Get the last successful entry & timestamp for that entry
        last_save = successful_saves[-1]
        r = re.search("\d\d\d\d\d\d\d\d\d\d\d\d\d\d", last_save)
        timestamp = r.group()
        # Generate the URL for the last successful save's raw HTML file
        last_save_url = f'https://web.archive.org/web/{timestamp}id_/{site}'
        # Now that we have the timestamp for the last successful wayback entry, we can pull the HTML
        last_save_html = requests.get(last_save_url)
        # And pass it to BeautifulSoup to view only the css selectors we care about.
        soup = BeautifulSoup(last_save_html.text, 'html.parser')
        old_elements = soup.select(selector)
        # Now going to pull the current version of the site & pull selectors using bsoup
        current_html = requests.get(site)
        soup2 = BeautifulSoup(current_html.text, 'html.parser')
        new_elements = soup2.select(selector)
        # If there are no differences between the current site and the last archived site, Add-On ends.
        if old_elements == new_elements:
            self.set_message("No changes in page since last archive")
            sys.exit(0)
        else:
            # Generating a list of strings using prettify to pass to difflib
            old_tags = []
            for x in old_elements:
                old_tags.append(x.prettify()) 
            # Generating a list of strings using prettify to pass to difflib 
            new_tags = [] 
            for y in new_elements:
                new_tags.append(y.prettify())
            # Generates HTML view that shows diffs in a pretty format
            html_diff = dl.HtmlDiff().make_file(old_tags, new_tags, context=True)
            
            # Sends the diff as an alert to the user's email -- need to add HTML support to email for this to work correctly
            # self.send_mail("Klaxon Alert: Site Updated", html_diff)
            Path('diff.html').write_text(html_diff)
            self.upload_file(open("diff.html"))
            # Captures the more recent version of the site in Wayback. 
            savepagenow.capture(site)

    def main(self):
        site = self.data.get("site")
        selector = self.data.get("selector")
        self.monitor_with_selector(site, selector)

if __name__ == "__main__":
    Klaxon().main()
