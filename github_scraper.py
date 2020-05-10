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

    Use Github API key and user name to make requests to Github API.
    Create spreadsheets named after data type and date.

    Attributes:
        api_token (str): Github API token necessary for authentication
        members (Dict[str, List[str]]): Dict with orgs as keys and list of members as values
        orgs (List[str]): List of organizational Github accounts to scrape
        timestamp (str): Current date and hour, used to create unique file names
        user (str): Name of GitHub user that scrapes the data
    """

    def __init__(self) -> None:
        """Instantiate object.

        Read config file and org list, get list of organizations' members and
        get current time.

        Raises:
            KeyError: If config file is empty
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
            print("\nFailed to read user name and password from config.jon file.")
            print("Please enter your Github user name and API token.")
            exit(1)

        # Read list of organizations from file
        print("\nReading list of organizations from file...")
        self.orgs = []
        with open('organizations.txt', 'r') as file:
            for line in file:
                # Using rstrip to remove the newline escape sequences
                self.orgs.append(line.rstrip('\n'))
        if not self.orgs:
            print("\nNo organizations to scrape found in organizations.txt.")
            print("Please add the names of the organizations you want to scrape.")
            print("Add one name per line.")
            exit(1)

        # Members of listed organizations. Instantiated as empty dict and only loaded
        # if user selects operation that needs this list. Saves API calls.
        self.members: Dict[str, List[str]] = {}

        # Timestamp used to name files
        self.timestamp = time.strftime('%Y-%m-%d_%H:%M:%S')

        # Start user interface
        self.select_options()

    def get_members(self) -> Dict[str, List[str]]:
        """Get list of members of specified orgs.

        Returns:
            Dict[str, List[str]]: Keys are orgs, values list of members
        """
        print("\nCollecting members of specified organizations...")
        members: Dict[str, List[str]] = {}
        for org in self.orgs:
            json_org_members = self.load_json(
                f"https://api.github.com/orgs/{org}/members"
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
            1: self.get_org_repos,
            2: self.get_repo_contributors,
            3: self.get_members_repos,
            4: self.get_members_info,
            5: self.get_starred_repos,
            6: self.generate_follower_network,
            7: self.generate_memberships_network
        }
        # Check if member scrape is required
        if any(int(item) for item in operations_input if int(item) in [3, 4, 5, 6, 7]):
            self.members = self.get_members()
        for operation in operations_input:
            operations_dict[int(operation)]()

    def load_json(self, url: str, memberscrape: bool = False):
        """Load json file using requests.

        Iterates over the pages of the API and returns a list of dicts.

        Args:
            url (str): Github API URL to load as JSON
            memberscrape (bool, optional): Scraping members requires different URL

        Returns:
            JSON object: Github URL loaded as JSON
        """
        # TODO: Add error handling if request fails (e.g. if repo was not found)
        if memberscrape:
            json_data = requests.get(
                f"{url}?per_page=100",
                auth=(self.user, self.api_token)
            ).json()
            return json_data

        page = 1
        json_list = []
        page_not_empty = True
        while page_not_empty:
            json_data = requests.get(
                f"{url}?per_page=100&page={str(page)}",
                auth=(self.user, self.api_token)
            ).json()
            if json_data == []:
                page_not_empty = False
            else:
                json_list.extend(json_data)
                page += 1
        return json_list

    def generate_csv(self, file_name: str, json_list: List, columns_list: List):
        """Write CSV file.

        Args:
            file_name (str): Name of the CSV file
            json_list (List): JSON data to turn into CSV
            columns_list (List): List of columns that represent relevant fields
                                 in the JSON data
        """
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

    def get_org_repos(self):
        """Create list of the organizations' repositories."""
        print("\nScraping repositories")
        json_repos = []
        for org in self.orgs:
            print(f"Scraping repositories of {org}")
            json_repo = self.load_json(
                f"https://api.github.com/orgs/{org}/repos"
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

    def get_repo_contributors(self):
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
                f"https://api.github.com/orgs/{org}/repos"
            )
            for repo in json_repo:
                try:
                    print(f"Getting contributors of {repo['name']}")
                    # First, add repo as a node to the graph
                    graph.add_node(repo['name'], organization=org)
                    # Then get a list of contributors
                    json_contributors_repo = self.load_json(
                        f"https://api.github.com/repos/{org}/{repo['name']}/contributors"
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
                    f"https://api.github.com/users/{member}/repos"
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
                    f"https://api.github.com/users/{member}",
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
                    f"https://api.github.com/users/{member}/starred"
                )
                for repo in json_starred_repos_member:
                    repo['organization'] = org
                    repo['user'] = member
                    json_starred_repos_all.append(repo)
        file_name = f"starred_repositories_{self.timestamp}.csv"
        self.generate_csv(file_name, json_starred_repos_all, columns_list)

    def generate_follower_network(self):
        """Create full or narrow follower networks of organizations' members.

        Get every user following the members of organizations (followers)
        and the users they are following themselves (following). Then generate two
        directed graphs with networkx. Only includes members of specified organizations
        if in narrow follower network.
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
                    f"https://api.github.com/users/{member}/followers"
                )
                json_followings = self.load_json(
                    f"https://api.github.com/users/{member}/following"
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

    def generate_memberships_network(self):
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
                    f"https://api.github.com/users/{member}/orgs"
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
