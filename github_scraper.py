"""Scrape GitHub data for organizational accounts."""

import csv
import json
import time
from sys import exit
from typing import List

import networkx as nx
import requests


class GithubScraper():
    """Scrape information about organizational Github accounts.

    Uses Github API key and user name to make requests to Github API.
    Creates spreadsheets named after data type and date.
    """

    def __init__(self) -> None:
        """Read config data and org list to instantiate.

        Attributes
            user : str
                Name of GitHub user that scrapes the data
            api_token : str
                Github API token necessary for authentication
            orgs : List
                List of organizational Github accounts to scrape
        """
        # Read user name and API token from config file
        try:
            with open('config.json', 'r') as file:
                config = json.load(file)
                self.user = config['user_name']
                self.api_token = config['api_token']
                if self.user == "" or self.api_token == "":
                    raise KeyError
                print(f"User name: {self.user}")
                print(f"Api token: {self.api_token}")
        except (FileNotFoundError, KeyError):
            print("Failed to read user name and password in config.jon file.")
            exit(1)

        # Read list of organizations from file
        print("\nReading list of organizations from file.\n")
        self.orgs = []
        with open('organizations.txt', 'r') as file:
            for line in file:
                # Using rstrip to remove the newline escape sequences
                self.orgs.append(line.rstrip('\n'))

        # Start user interface
        self.select_options()

    def select_options(self):
        """Show menu that lets user select scraping option(s)."""
        print("Will scrape data from the following organizations:", *self.orgs)
        print("""
        1. Get a list of the organizations' repositories (CSV)
        2. Get all contributors of the organizations' repositories (CSV and GEXF).
        3. Get a list of the repositories of all the members of the organizations (CSV).
        4. Get information for each member of the organizations (CSV).
        5. Generate spreadsheet for starred repositories (CSV).
        6. Generate a full follower network (GEXF).
        7. Generate a narrow follower network (only includes members of the organizations) (GEXF).
        8. Generate a graph illustrating the membership structures (GEXF).
        """)
        operations = input(
            "Choose options. Select multiple with comma separated list or 'All'.\n> "
        )

        # Read input and start specified operations
        operations = operations.lower()
        if operations == 'all':
            operations = "1, 2, 3, 4, 5, 6, 7, 8"
        operations_input = operations.split(', ')
        operations_dict = {
            1: self.get_repos,
            2: self.get_contributors,
            3: self.get_members_repos,
            4: self.get_members_info,
            5: self.get_starred_repos,
            6: self.generate_follower_network,
            7: self.generate_follower_network,
            8: self.generate_memberships
        }
        for operation in operations_input:
            if int(operation) == 6:
                operations_dict[int(operation)](network_type="full")
            elif int(operation) == 7:
                operations_dict[int(operation)](network_type="narrow")
            else:
                operations_dict[int(operation)]()

    def load_json(self, url: str, memberscrape: bool = False):
        """Load json file using requests.

        Iterates over the pages of the API and returns a list of dicts.
        """
        # TODO: Add error handling if request fails (e.g. if repo was not found)
        if memberscrape:
            request = requests.get(
                url,
                auth=(self.user, self.api_token)
            )
            json_data = json.loads(request.text)
            return json_data

        page = 1
        json_list = []
        page_not_empty = True
        while page_not_empty:
            request = requests.get(
                f"{url}&page={str(page)}",
                auth=(self.user, self.api_token)
            )
            json_data = json.loads(request.text)
            if json_data == []:
                page_not_empty = False
            else:
                json_list.extend(json_data)
                page += 1
        return json_list

    def generate_csv(self, data_type: str, json_list: List, columns_list: List):
        """Write CSV file."""
        with open(
                f"data/{data_type}_{time.strftime('%Y-%m-%d_%H:%M:%S')}.csv",
                'a+'
        ) as file:
            csv_file = csv.DictWriter(
                file,
                fieldnames=columns_list,
                extrasaction="ignore"
            )
            csv_file.writeheader()
            for item in json_list:
                csv_file.writerow(item)
        print(
            f"\nCSV file saved as data/{data_type}_{time.strftime('%Y-%m-%d_%H:%M:%S')}.csv"
        )

    def get_repos(self):
        """Create list of the organizations' repositories."""
        # TODO: Create helper function to load API pages
        json_repos = []
        for org in self.orgs:
            print(f"\nScraping repositories of {org}")
            json_repo = self.load_json(
                f"https://api.github.com/orgs/{org}/repos?per_page=100"
            )
            for repo in json_repo:
                # Add field for org to make CSV file more useful
                repo['organization'] = org
                json_repos.append(repo)
        # Create a list with the items I'm interested in, then call generate_csv
        columns_list = [
            'organization',
            'name',
            'full_name',
            'stargazers_count',
            'language',
            'created_at',
            'updated_at',
            'homepage',
            'fork',
            'description'
        ]
        self.generate_csv("repo-list", json_repos, columns_list)

    def get_contributors(self):
        """Create list of contributors to the organizations' repositories."""
        print("\nCreating list of contributors.")
        json_contributors_all = []
        graph = nx.DiGraph()
        columns_list = [
            'organization',
            'repository',
            'login',
            'contributions',
            'html_url',
            'url'
        ]
        for org in self.orgs:
            print(f"\nScraping contributors of {org}")
            json_repo = self.load_json(
                f"https://api.github.com/orgs/{org}/repos?per_page=100"
            )
            for repo in json_repo:
                try:
                    print(f"Getting contributors of {repo['name']}")
                    # First, add repo as a node to the graph
                    graph.add_node(repo['name'], organization=org)
                    # Then get a list of contributors
                    json_contributors_repo = self.load_json(
                        f"https://api.github.com/repos/{org}/{repo['name']}/contributors?per_page=100"
                    )
                    for contributor in json_contributors_repo:
                        # Add each contributor as an edge to the graph
                        graph.add_edge(
                            contributor['login'],
                            repo['name'],
                            organization=org
                        )
                        # Prepare CSV and add fields to make it more usable
                        contributor["organization"] = org
                        contributor["repository"] = repo["name"]
                        json_contributors_all.append(contributor)
                except json.decoder.JSONDecodeError:
                    # If repository is empty, inform user and pass
                    print(
                        f"Repository '{repo['name']}' appears to be empty."
                    )
        self.generate_csv("contributor-list", json_contributors_all, columns_list)
        # TODO: Use variable for name of the file
        nx.write_gexf(
            graph,
            f"data/contributor-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
        )
        print(
            f"\nSaved graph file: data/contributor-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
        )

    def get_members_repos(self):
        """Create list of all the members of an organization and their repositories."""
        print("\nGetting repositories of all members.")
        json_members_repos = []
        columns_list = [
            'organization',
            'user',
            'full_name',
            'fork',
            'stargazers_count',
            'forks_count',
            'language',
            'description'
        ]
        for org in self.orgs:
            print(f"\nGetting members of {org}")
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in json_org_members:
                print(f"Getting repositories of {member['login']}")
                json_repos_members = self.load_json(
                    f"https://api.github.com/users/{member['login']}/repos?per_page=100"
                )
                for repo in json_repos_members:
                    # Add fields to make CSV file more usable
                    repo['organization'] = org
                    repo['user'] = member['login']
                    json_members_repos.append(repo)
        self.generate_csv("members-list", json_members_repos, columns_list)

    def get_members_info(self):
        """Gather information about the organizations' members."""
        print("\nGetting user information of all members.")
        json_members_info = []
        columns_list = [
            'organization',
            'login',
            'name',
            'url',
            'type',
            'company',
            'blog',
            'location'
        ]
        for org in self.orgs:
            print(f"\nGetting members of {org}")
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in json_org_members:
                print(f"Getting user information for {member['login']}")
                json_org_member = self.load_json(
                    f"https://api.github.com/users/{member['login']}?per_page=100",
                    memberscrape=True
                )
                # Add field to make CSV file more usable
                json_org_member["organization"] = org
                json_members_info.append(json_org_member)
        self.generate_csv("members-info", json_members_info, columns_list)

    def get_starred_repos(self):
        """Create list of all the repositories starred by organizations' members."""
        print("\nGetting repositories starred by members.")
        json_starred_repos_all = []
        columns_list = [
            'organization',
            'user',
            'full_name',
            'html_url',
            'language',
            'description'
        ]
        for org in self.orgs:
            print(f"\nGetting members of {org}")
            json_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in json_members:
                print(f"Getting starred repositories of {member['login']}")
                json_starred_repos_member = self.load_json(
                    f"https://api.github.com/users/{member['login']}/starred?per_page=100"
                )
                for repo in json_starred_repos_member:
                    repo['organization'] = org
                    repo['user'] = member['login']
                    json_starred_repos_all.append(repo)
        self.generate_csv("starred-list", json_starred_repos_all, columns_list)

    def generate_follower_network(self, network_type: str = ""):
        """Create full or narrow follower networks of organizations' members.

        First, get every user following the members of organizations (followers)
        and the users they are following themselves (following). Then generate a
        directed graph with networkx. Only includes members of specified organizations
        if network_type == narrow.
        """
        if network_type == "full":
            print("\nGenerating full follower network.")
        else:
            print("\nGenerating narrow follower network.")
            # Getting a list of all members if narrow graph is chosen
            members_list = []
            for org in self.orgs:
                print("\nGetting members of specified organizations to filter network...")
                json_org_members = self.load_json(
                    f"https://api.github.com/orgs/{org}/members?per_page=100"
                )
                for member in json_org_members:
                    members_list.append(member['login'])

        graph = nx.DiGraph()
        for org in self.orgs:
            print(f"\nGetting members of {org}")
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in json_org_members:
                json_followers = self.load_json(
                    f"https://api.github.com/users/{member['login']}/followers?per_page=100"
                )
                json_followings = self.load_json(
                    f"https://api.github.com/users/{member['login']}/following?per_page=100"
                )
                print(f"Getting follower network of {member['login']}")
                graph.add_node(member['login'], organization=org)
                if network_type == "full":
                    for follower in json_followers:
                        graph.add_edge(
                            follower['login'],
                            member['login'],
                            organization=org
                        )
                    for following in json_followings:
                        graph.add_edge(
                            member['login'],
                            following['login'],
                            organization=org
                        )
                else:
                    # Generate narrow network excluding non-members
                    for follower in json_followers:
                        if follower['login'] in members_list:
                            graph.add_edge(
                                follower['login'],
                                member['login'],
                                organization=org
                            )
                    for following in json_followings:
                        if following['login'] in members_list:
                            graph.add_edge(
                                member['login'],
                                following['login'],
                                organization=org
                            )
        nx.write_gexf(
            graph,
            f"data/{network_type}-follower-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
        )
        print(
            "\nSaved graph file: data/"
            f"{network_type}-follower-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
        )

    def generate_memberships(self):
        """Take all the members of the organizations and generate a directed graph.

        This shows creates a network with the organizational memberships.
        """
        print("\nGenerating network of memberships.")
        graph = nx.DiGraph()
        for org in self.orgs:
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in json_org_members:
                print(f"Getting membership of {member['login']}")
                graph.add_node(member['login'], node_type='user')
                json_org_memberships = self.load_json(
                    f"https://api.github.com/users/{member['login']}/orgs?per_page=100"
                )
                for organization in json_org_memberships:
                    graph.add_edge(
                        member['login'],
                        organization['login'],
                        node_type='organization'
                    )
        nx.write_gexf(
            graph,
            f"data/membership-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf")
        print(
            f"\nSaved graph file: data/membership-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
        )


if __name__ == "__main__":
    GithubScraper()
