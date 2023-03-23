"""
This is the Klaxon Site Monitor Add-On, that allows you to monitor webpages for changes and get alerted if portions of the page change. 
"""

from documentcloud.addon import AddOn
from bs4 import BeautifulSoup
import requests
import savepagenow

class Klaxon(AddOn):
    """Add-On that will monitor a site for changes and alert you for updates"""
    
    def monitor_with_selector(site, selector):
        
    
    def full_page_monitor(site):
        params = {'url':site}
        response = requests.get('http://web.archive.org/cdx/search/cdx', params=params)
        successul_saves = []
        for line in response.text.splitlines():
            if ' 200 ' in line:
                successful_saves.append(line)
        last_save = successful_saves[-1]
        timestamp = last_save.split('/')[1].split('h')[0].strip()
        # Now that we have the timestamp for the last successful wayback entry, we can pull the HTML
        response = requests.get(f'https://web.archive.org/web/{timestamp}/{site}')
    
    def main(self):
        site = self.data.get("site")
        selector = self.data.get("selector")
        if selector is None:
            monitor_with_selector(site, selector)
        else:
            full_page_monitor(site)
        
        self.send_mail("Hello World!", "We finished!")


if __name__ == "__main__":
    Klaxon().main()
