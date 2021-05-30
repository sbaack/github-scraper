"""Scrape GitHub data for organizational accounts."""

import argparse
import asyncio
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import aiohttp
import networkx as nx


class GithubScraper():
    """Scrape information about organizational Github accounts.

    Use Github API key and user name to make requests to Github API.
    Create spreadsheets named after data type and date.

    Attributes:
        orgs (List[str]): List of organizational Github accounts to scrape
        session (aiohttp.ClientSession): Session using Github user name and API token
    """

    def __init__(self, organizations: List[str],
                 session: aiohttp.ClientSession) -> None:
        """Instantiate object."""
        self.orgs = organizations
        self.session = session
        # Members of listed organizations. Instantiated as empty dict and only loaded
        # if user selects operation that needs this list. Saves API calls.
        self.members: Dict[str, List[str]] = {}
        # Directory to store scraped data with timestamp
        self.data_directory: Path = Path(
            Path.cwd(), 'data', time.strftime('%Y-%m-%d_%H-%M-%S')
        )
        Path(self.data_directory).mkdir()

    async def get_members(self) -> Dict[str, List[str]]:
        """Get list of members of specified orgs.

        Returns:
            Dict[str, List[str]]: Keys are orgs, values list of members
        """
        print("Collecting members of specified organizations...")
        members: Dict[str, List[str]] = {}
        for org in self.orgs:
            json_org_members = await self.load_json(
                f"https://api.github.com/orgs/{org}/members"
            )
            members[org] = []
            for member in json_org_members:
                members[org].append(member['login'])
        return members

    async def load_json(self, url: str) -> List[Dict[str, Any]]:
        """Load json file using requests.

        Makes API calls and returns JSON results.

        Args:
            url (str): Github API URL to load as JSON

        Returns:
            List[Dict[str, Any]]: Github URL loaded as JSON
        """
        page: int = 1
        json_list: List[Dict[str, Any]] = []
        # Scraping member information only requires one request
        if url.split("/")[-2] == 'users':
            resp = await self.session.get(f"{url}?per_page=100")
            json_data = await resp.json()
            json_list.append(json_data)
            return json_list
        # Other requests require pagination
        while True:
            resp = await self.session.get(f"{url}?per_page=100&page={str(page)}")
            json_data = await resp.json()
            if json_data == []:
                break
            json_list.extend(json_data)
            page += 1
        return json_list

    def generate_csv(self, file_name: str, json_list: List[Dict[str, Any]],
                     columns_list: List) -> None:
        """Write CSV file.

        Args:
            file_name (str): Name of the CSV file
            json_list (List[Dict[str, Any]]): JSON data to turn into CSV
            columns_list (List): List of columns that represent relevant fields
                                 in the JSON data
        """
        with open(
                Path(self.data_directory, file_name),
                'a+',
                encoding='utf-8'
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
            f"- file saved as {Path('data', self.data_directory.name, file_name)}"
        )

    async def get_org_repos(self) -> None:
        """Create list of the organizations' repositories."""
        #TODO: Don't write CSV here, just return repos and make
        #      a separate function that writes the CSV file. This way
        #      you can avoid scraping repos twice (again in get_repo_contributors)
        print("Scraping repositories")
        json_repos: List[Dict[str, Any]] = []
        for org in self.orgs:
            json_repo = await self.load_json(
                f"https://api.github.com/orgs/{org}/repos")
            for repo in json_repo:
                # Add field for org to make CSV file more useful
                repo['organization'] = org
                json_repos.append(repo)
        # Create list of items that should appear as columns in the CSV
        scraping_items: List[str] = [
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
        self.generate_csv('org_repositories.csv', json_repos, scraping_items)

    async def get_repo_contributors(self) -> None:
        """Create list of contributors to the organizations' repositories."""
        print("Scraping contributors")
        json_contributors_all: List[Dict[str, Any]] = []
        graph = nx.DiGraph()
        scraping_items: List[str] = [
            'organization',
            'repository',
            'login',
            'contributions',
            'html_url',
            'url'
        ]
        for org in self.orgs:
            json_repo = await self.load_json(f"https://api.github.com/orgs/{org}/repos")
            for repo in json_repo:
                try:
                    # First, add repo as a node to the graph
                    graph.add_node(repo['name'], organization=org)
                    # Then get a list of contributors
                    json_contributors_repo = await self.load_json(
                        "https://api.github.com/repos/"
                        f"{org}/{repo['name']}/contributors"
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
                except aiohttp.ContentTypeError:
                    # If repository is empty, pass
                    pass
        self.generate_csv('contributor_list.csv', json_contributors_all, scraping_items)
        nx.write_gexf(
            graph,
            Path(self.data_directory, 'contributor_network.gexf')
        )
        print(
            "- file saved as "
            f"{Path('data', self.data_directory.name, 'contributor_network.gexf')}"
        )

    async def get_members_repos(self) -> None:
        """Create list of all the members of an organization and their repositories."""
        print("Getting repositories of all members.")
        json_members_repos: List[Dict[str, Any]] = []
        scraping_items: List[str] = [
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
            for member in self.members[org]:
                json_repos_members = await self.load_json(
                    f"https://api.github.com/users/{member}/repos")
                for repo in json_repos_members:
                    # Add fields to make CSV file more usable
                    repo['organization'] = org
                    repo['user'] = member
                    json_members_repos.append(repo)
        self.generate_csv('members_repositories.csv',
                          json_members_repos, scraping_items)

    async def get_members_info(self) -> None:
        """Gather information about the organizations' members."""
        print("Getting user information of all members.")
        json_members_info: List[Dict[str, Any]] = []
        scraping_items: List[str] = [
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
            for member in self.members[org]:
                # Don't use self.load_json() because pagination method
                # does not work on API calls for member infos
                json_org_member = await self.load_json(
                    f"https://api.github.com/users/{member}")
                # Add field to make CSV file more usable
                json_org_member[0]["organization"] = org
                json_members_info.extend(json_org_member)
        self.generate_csv('members_info.csv', json_members_info, scraping_items)

    async def get_starred_repos(self) -> None:
        """Create list of all the repositories starred by organizations' members."""
        print("Getting repositories starred by members.")
        json_starred_repos_all: List[Dict[str, Any]] = []
        scraping_items: List[str] = [
            'organization',
            'user',
            'full_name',
            'html_url',
            'language',
            'description'
        ]
        for org in self.orgs:
            for member in self.members[org]:
                json_starred_repos_member = await self.load_json(
                    f"https://api.github.com/users/{member}/starred")
                for repo in json_starred_repos_member:
                    repo['organization'] = org
                    repo['user'] = member
                    json_starred_repos_all.append(repo)
        self.generate_csv('starred_repositories.csv',
                          json_starred_repos_all, scraping_items)

    async def generate_follower_network(self) -> None:
        """Create full or narrow follower networks of organizations' members.

        Get every user following the members of organizations (followers)
        and the users they are following themselves (following). Then generate two
        directed graphs with NetworkX. Only includes members of specified organizations
        if in narrow follower network.
        """
        print('Generating follower networks')
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
            for member in self.members[org]:
                json_followers = await self.load_json(
                    f"https://api.github.com/users/{member}/followers")
                json_followings = await self.load_json(
                    f"https://api.github.com/users/{member}/following")
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
                Path(self.data_directory, f"{graph_type}-follower-network.gexf")
            )
        print(
            f"- files saved in {Path('data', self.data_directory.name)} as "
            "full-follower-network.gexf and narrow-follower-network.gexf"
        )

    async def generate_memberships_network(self) -> None:
        """Take all the members of the organizations and generate a directed graph.

        This shows creates a network with the organizational memberships.
        """
        print("Generating network of memberships.")
        graph = nx.DiGraph()
        for org in self.orgs:
            for member in self.members[org]:
                graph.add_node(member, node_type='user')
                json_org_memberships = await self.load_json(
                    f"https://api.github.com/users/{member}/orgs")
                for organization in json_org_memberships:
                    graph.add_edge(
                        member,
                        organization['login'],
                        node_type='organization'
                    )
        nx.write_gexf(
            graph,
            Path(self.data_directory, 'membership_network.gexf')
        )
        print(
            "- file saved as "
            f"{Path('data', self.data_directory.name, 'membership_network.gexf')}"
        )


def read_config() -> Tuple[str, str]:
    """Read config file.

    Returns:
        Tuple[str, str]: Github user name and API token

    Raises:
        KeyError: If config file is empty
    """
    try:
        with open(Path(Path.cwd(), 'config.json'), 'r', encoding='utf-8') as file:
            config = json.load(file)
            user: str = config['user_name']
            api_token: str = config['api_token']
            if user == "" or api_token == "":
                raise KeyError
            else:
                return user, api_token
    except (FileNotFoundError, KeyError):
        sys.exit("Failed to read Github user name and/or API token. "
                 "Please add them to the config.json file.")


def read_organizations() -> List[str]:
    """Read list of organizations from file.

    Returns:
        List[str]: List of names of organizational Github accounts
    """
    orgs: List[str] = []
    with open(Path(Path.cwd(), 'organizations.csv'), 'r', encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            orgs.append(row['github_org_name'])
    if not orgs:
        sys.exit("No organizations to scrape found in organizations.csv. "
                 "Please add the names of the organizations you want to scrape "
                 "in the column 'github_org_name' (one name per row).")
    return orgs


def parse_args() -> Dict[str, bool]:
    """Parse arguments.

    We use the 'dest' value to map args with functions/methods. This way, we
    can use getattr(object, dest)() and avoid long if...then list in main().

    Returns:
        Dict[str, bool]: Result of vars(parse_args())
    """
    argparser = argparse.ArgumentParser(
        description="Scrape organizational accounts on Github."
    )
    argparser.add_argument(
        "--all",
        "-a",
        action="store_true",
        help="scrape all the information listed below"
    )
    argparser.add_argument(
        "--repos",
        "-r",
        action='store_true',
        dest="get_org_repos",
        help="scrape the organizations' repositories (CSV)"
    )
    argparser.add_argument(
        "--contributors",
        "-c",
        action="store_true",
        dest="get_repo_contributors",
        help="scrape contributors of the organizations' repositories (CSV and GEXF)"
    )
    argparser.add_argument(
        "--member_repos",
        "-mr",
        action="store_true",
        dest="get_members_repos",
        help="scrape all repositories owned by the members of the organizations (CSV)"
    )
    argparser.add_argument(
        "--member_infos",
        "-mi",
        action="store_true",
        dest="get_members_info",
        help="scrape information about each member of the organizations (CSV)"
    )
    argparser.add_argument(
        "--starred",
        "-s",
        action="store_true",
        dest="get_starred_repos",
        help="scrape all repositories starred by the members of the organizations (CSV)"
    )
    argparser.add_argument(
        "--followers",
        "-f",
        action="store_true",
        dest="generate_follower_network",
        help="generate a follower network. Creates full and narrow network graph, the "
             "latter only shows how scraped organizations are networked among each "
             "other (two GEXF files)"
    )
    argparser.add_argument(
        "--memberships",
        "-m",
        action="store_true",
        dest="generate_memberships_network",
        help="scrape all organizational memberships of org members (GEXF)"
    )
    args: Dict[str, bool] = vars(argparser.parse_args())
    return args


async def main() -> None:
    """Set up GithubScraper object."""
    args: Dict[str, bool] = parse_args()
    if not any(args.values()):
        sys.exit("You need to provide at least one argument. "
                 "For usage, call: github_scraper -h")
    user, api_token = read_config()
    organizations = read_organizations()
    # To avoid unnecessary API calls, only get org members if called functions needs it
    require_members = ['get_members_repos', 'get_members_info', 'get_starred_repos',
                       'generate_follower_network', 'generate_memberships_network']
    # Start aiohttp session
    auth = aiohttp.BasicAuth(user, api_token)
    async with aiohttp.ClientSession(auth=auth) as session:
        github_scraper = GithubScraper(organizations, session)
        # If --all was provided, simply run everything
        if args['all']:
            github_scraper.members = await github_scraper.get_members()
            for arg in args:
                if arg != 'all':
                    await getattr(github_scraper, arg)()
        else:
            # Check what args provided, get members if necessary, call related methods
            called_args = [arg for arg, value in args.items() if value]
            if any(arg for arg in called_args if arg in require_members):
                github_scraper.members = await github_scraper.get_members()
            for arg in called_args:
                await getattr(github_scraper, arg)()


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
