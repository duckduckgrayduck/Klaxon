"""
This is the Klaxon Site Monitor Add-On, that allows you to monitor webpages for changes and get alerted if portions of the page change. 
"""

from documentcloud.addon import AddOn
from bs4 import BeautifulSoup
import requests
import savepagenow

class Klaxon(AddOn):
    """Add-On that will monitor a site for changes and alert you for updates"""

    def main(self):
        site = self.data.get("site")
        project = self.data["project"]
        # if project is an integer, use it as a project ID
        try:
            self.project = int(project)
        except ValueError:
            project, created = self.client.projects.get_or_create_by_title(project)
            self.project = project.id
        
        self.send_mail("Hello World!", "We finished!")


if __name__ == "__main__":
    Klaxon().main()
