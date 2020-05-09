"""Scrape GitHub data for organizational accounts."""

import csv
import json
import time
from sys import exit
from typing import Dict, List

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
        print("\nReading list of organizations from file...")
        self.orgs = []
        with open('organizations.txt', 'r') as file:
            for line in file:
                # Using rstrip to remove the newline escape sequences
                self.orgs.append(line.rstrip('\n'))

        # Load members of the listed organizations
        self.members = self.get_members()

        # Timestamp used to name files
        self.timestamp = time.strftime('%Y-%m-%d_%H:%M:%S')

        # Start user interface
        self.select_options()

    def get_members(self):
        """Get list of members of specified orgs."""
        print("Collecting members of specified organizations...\n")
        members: Dict[str, List[str]] = {}
        for org in self.orgs:
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            members[org] = []
            for member in json_org_members:
                members[org].append(member['login'])
        return members

    def select_options(self):
        """Show menu that lets user select scraping option(s)."""
        print("Will scrape data from the following organizations:", *self.orgs)
        print("""
        1. Scrape the organizations' repositories (CSV).
        2. Scrape contributors of the organizations' repositories (CSV and GEXF).
        3. Scrape all repositories owned by the members of the organizations (CSV).
        4. Scrape information about each member of the organizations (CSV).
        5. Scrape all repositories starred by the members of the organizations (CSV).
        6. Generate a follower network. Creates full and narrow network graph, the latter only
           shows how scraped organizations are networked among each other (two GEXF files).
        7. Scrape all organizational memberships to graph membership structures (GEXF).
        """)
        operations = input(
            "Choose option(s). Select multiple with comma separated list or 'All'.\n> "
        )

        # Read input and start specified operations
        operations = operations.lower()
        if operations == 'all':
            operations = "1, 2, 3, 4, 5, 6, 7"
        operations_input = operations.split(', ')
        operations_dict = {
            1: self.get_repos,
            2: self.get_contributors,
            3: self.get_members_repos,
            4: self.get_members_info,
            5: self.get_starred_repos,
            6: self.generate_follower_network,
            7: self.generate_memberships
        }
        for operation in operations_input:
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

    def generate_csv(self, file_name: str, json_list: List, columns_list: List):
        """Write CSV file."""
        with open(
                f"data/{file_name}",
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
            f"\nCSV file saved as data/{file_name}"
        )

    def get_repos(self):
        """Create list of the organizations' repositories."""
        print("\nScraping repositories")
        json_repos = []
        for org in self.orgs:
            print(f"Scraping repositories of {org}")
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
        file_name = f"org_repositories_{self.timestamp}.csv"
        self.generate_csv(file_name, json_repos, columns_list)

    def get_contributors(self):
        """Create list of contributors to the organizations' repositories."""
        print("\nScraping contributors")
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
        file_name = f"contributor_list_{self.timestamp}.csv"
        self.generate_csv(file_name, json_contributors_all, columns_list)
        # TODO: Use variable for name of the file
        nx.write_gexf(
            graph,
            f"data/contributor_network_{self.timestamp}.gexf"
        )
        print(
            f"\nSaved graph file: data/contributor_network_{self.timestamp}.gexf"
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
            print(f"\nScraping {org}...")
            for member in self.members[org]:
                print(f"Getting repositories of {member}")
                json_repos_members = self.load_json(
                    f"https://api.github.com/users/{member}/repos?per_page=100"
                )
                for repo in json_repos_members:
                    # Add fields to make CSV file more usable
                    repo['organization'] = org
                    repo['user'] = member
                    json_members_repos.append(repo)
        file_name = f"members_repositories_{self.timestamp}.csv"
        self.generate_csv(file_name, json_members_repos, columns_list)

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
            print(f"\nScraping {org}...")
            for member in self.members[org]:
                print(f"Getting user information for {member}")
                json_org_member = self.load_json(
                    f"https://api.github.com/users/{member}?per_page=100",
                    memberscrape=True
                )
                # Add field to make CSV file more usable
                json_org_member["organization"] = org
                json_members_info.append(json_org_member)
        file_name = f"members_info_{self.timestamp}.csv"
        self.generate_csv(file_name, json_members_info, columns_list)

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
            print(f"\nScraping {org}...")
            for member in self.members[org]:
                print(f"Getting starred repositories of {member}")
                json_starred_repos_member = self.load_json(
                    f"https://api.github.com/users/{member}/starred?per_page=100"
                )
                for repo in json_starred_repos_member:
                    repo['organization'] = org
                    repo['user'] = member
                    json_starred_repos_all.append(repo)
        file_name = f"starred_repositories_{self.timestamp}.csv"
        self.generate_csv(file_name, json_starred_repos_all, columns_list)

    def generate_follower_network(self):
        """Create full or narrow follower networks of organizations' members.

        First, get every user following the members of organizations (followers)
        and the users they are following themselves (following). Then generate a
        directed graph with networkx. Only includes members of specified organizations
        if network_type == narrow.
        """
        print('\nGenerating follower networks')
        # Create graph dict and add self.members as nodes
        graph: Dict[str, nx.DiGraph] = {}
        graph["full"] = nx.DiGraph()
        graph["narrow"] = nx.DiGraph()
        for org in self.orgs:
            for member in self.members[org]:
                for graph_type in graph:
                    graph[graph_type].add_node(member, organization=org)

        # Get followers and following for each member and build graph
        for org in self.orgs:
            print(f"\nScraping {org}...")
            for member in self.members[org]:
                json_followers = self.load_json(
                    f"https://api.github.com/users/{member}/followers?per_page=100"
                )
                json_followings = self.load_json(
                    f"https://api.github.com/users/{member}/following?per_page=100"
                )
                print(f"Getting follower network of {member}")

                # First generate full follower network
                for follower in json_followers:
                    graph["full"].add_edge(
                        follower['login'],
                        member,
                        organization=org
                    )
                    # Then generate narrow follower network
                    if follower['login'] in self.members[org]:
                        graph["narrow"].add_edge(
                            follower['login'],
                            member,
                            organization=org
                        )
                for following in json_followings:
                    graph["full"].add_edge(
                        member,
                        following['login'],
                        organization=org
                    )
                    if following['login'] in self.members[org]:
                        graph["narrow"].add_edge(
                            member,
                            following['login'],
                            organization=org
                        )

        for graph_type in graph:
            nx.write_gexf(
                graph[graph_type],
                f"data/{graph_type}-follower-network_{self.timestamp}.gexf"
            )

        print(
            "\nSaved graph files in data folder:\n"
            f"- full-follower-network_{self.timestamp}.gexf\n"
            f"- narrow-follower-network_{self.timestamp}.gexf"
        )

    def generate_memberships(self):
        """Take all the members of the organizations and generate a directed graph.

        This shows creates a network with the organizational memberships.
        """
        print("\nGenerating network of memberships.\n")
        graph = nx.DiGraph()
        for org in self.orgs:
            for member in self.members[org]:
                print(f"Getting membership of {member}")
                graph.add_node(member, node_type='user')
                json_org_memberships = self.load_json(
                    f"https://api.github.com/users/{member}/orgs?per_page=100"
                )
                for organization in json_org_memberships:
                    graph.add_edge(
                        member,
                        organization['login'],
                        node_type='organization'
                    )
        nx.write_gexf(
            graph,
            f"data/membership_network_{self.timestamp}.gexf")
        print(
            f"\nSaved graph file: data/membership_network_{self.timestamp}.gexf"
        )


if __name__ == "__main__":
    GithubScraper()
