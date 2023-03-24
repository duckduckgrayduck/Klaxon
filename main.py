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
    
    #
    # This function is getting a little too large and dense - I think starting to
    # refactor it into multiple functions where appropriate would be good, as well
    # as just putting some new lines in places to break the code up into some sort
    # of logical "paragraphs" would make it more readable
    #
    
    def monitor_with_selector(self, site, selector):
        # Get the full list of archive.org entries
        response = requests.get(f'http://web.archive.org/cdx/search/cdx?url={site}')
        # Filter only for the successful entries
        successful_saves = []
        for line in response.text.splitlines():
            
            #
            # I am slightly worried about just searching for " 200 " somehow returning
            # a false positive if the format changes.  Maybe
            # line.split()[4] == "200"
            # would be more robust?  Not certain on this one.
            # Also, this for loop could be a list comprehension:
            #
            # succesful_saves = [
            #    line for line in response.text.splitlines()
            #    if line.split()[4] == "200"
            # ]
            #
            # I generally prefer list comprehensions, although if it is complex enough
            # a for loop may be easier to understand
            #
            
            if ' 200 ' in line:
                successful_saves.append(line)
        # Get the last successful entry & timestamp for that entry
        last_save = successful_saves[-1]
        
        # 
        # I believe this would be better written as:
        # r = re.search("\d{14}", last_save)
        #
        
        r = re.search("\d\d\d\d\d\d\d\d\d\d\d\d\d\d", last_save)
        timestamp = r.group()
        # Generate the URL for the last successful save's raw HTML file
        last_save_url = f'https://web.archive.org/web/{timestamp}id_/{site}'
        
        #
        # Going from url -> elements (lines 69 - 73 and 74 - 77) would
        # be a good candidate for factoring out into its own function
        #
        
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
            
            #
            # Another one where I think list comprehensions would be clearer:
            # old_tags = [x.prettify() for x in old_elements]
            # and similar for new_tags
            #
            
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
            resp = self.client.get(f"addon_runs/{self.id}/")
            file_url = resp.json()["file_url"]
            self.send_mail("Klaxon Alert: Site Updated", f"Get results here: {file_url}")

            # Captures the more recent version of the site in Wayback. 
            savepagenow.capture(site)

    def main(self):
        site = self.data.get("site")
        selector = self.data.get("selector")
        self.monitor_with_selector(site, selector)

if __name__ == "__main__":
    Klaxon().main()
