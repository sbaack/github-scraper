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

# TODO: Instead of DiGraph, use MultiDiGraph everywhere?


class GithubScraper:
    """Scrape information about organizational Github accounts.

    Use Github API key and user name to make requests to Github API.
    Create spreadsheets named after data type and date.

    Attributes:
        orgs (List[str]): List of organizational Github accounts to scrape
        session (aiohttp.ClientSession): Session using Github user name and API token
    """

    def __init__(
        self, organizations: List[str], session: aiohttp.ClientSession
    ) -> None:
        """Instantiate object."""
        self.orgs = organizations
        self.session = session
        # Members and repositories of listed organizations. Instantiated as empty dict
        # and only loaded if user selects operation that needs this list.
        # Saves API calls.
        self.members: Dict[str, List[str]] = {}
        self.repos: List[Dict[str, Any]] = []
        # Directory to store scraped data with timestamp
        self.data_directory: Path = Path(
            Path.cwd(), "data", time.strftime("%Y-%m-%d_%H-%M-%S")
        )
        Path(self.data_directory).mkdir()

    async def get_members(self) -> Dict[str, List[str]]:
        """Get list of members of specified orgs.

        Returns:
            Dict[str, List[str]]: Keys are orgs, values list of members
        """
        print("Collecting members of specified organizations...")
        members: Dict[str, List[str]] = {}
        tasks: List[asyncio.Task[Any]] = []
        for org in self.orgs:
            url = f"https://api.github.com/orgs/{org}/members"
            tasks.append(asyncio.create_task(self.call_api(url, organization=org)))
        json_org_members: List[Dict[str, Any]] = await self.load_json(tasks)
        # Extract names of org members from JSON data
        for org in self.orgs:
            members[org] = []
        for member in json_org_members:
            members[member["organization"]].append(member["login"])
        return members

    async def load_json(self, tasks: List[asyncio.Task[Any]]) -> List[Dict[str, Any]]:
        """Execute tasks with asyncio.wait() to make API calls.

        TODO: Catch when rate limit exceeded. Error message:

        {'documentation_url':
        'https://docs.github.com/rest/overview/resources-in-the-rest-api#rate-limiting',
        'message': 'API rate limit exceeded for user ID 8274140.'}

        TODO: Double check if you can get rid of try..except aiohttp.ContentTypeError
              and only call it in call_api instead

        Args:
            tasks (List[asyncio.Task[Any]]): List of awaitable tasks to execute

        Returns:
            List[Dict[str, Any]]: Full JSON returned by API
        """
        full_json: List[Dict[str, Any]] = []
        done, pending = await asyncio.wait(tasks, return_when="ALL_COMPLETED")
        for task in done:
            try:
                full_json.extend(await task)
            except aiohttp.ContentTypeError:
                # If repository is empty, pass
                pass
        return full_json

    async def call_api(self, url: str, **added_fields: str) -> List[Dict[str, Any]]:
        """Load json file using requests.

        Makes API calls and returns JSON results.

        Args:
            url (str): Github API URL to load as JSON
            **added_fields (str): Additional information that will be added to each item
                                  in the JSON data

        Returns:
            List[Dict[str, Any]]: Github URL loaded as JSON
        """
        page: int = 1
        json_data: List[Dict[str, Any]] = []
        # Requesting user info doesn't support pagination and returns dict, not list
        if url.split("/")[-2] == "users":
            async with self.session.get(f"{url}?per_page=100") as resp:
                member_json: Dict[str, Any] = await resp.json()
                # if "documentation_url" in member_json:
                #     sys.exit(member_json['message'])
                for key, value in added_fields.items():
                    member_json[key] = value
                json_data.append(member_json)
            return json_data
        # Other API calls return lists and should paginate
        while True:
            async with self.session.get(f"{url}?per_page=100&page={str(page)}") as resp:
                json_page: List[Dict[str, Any]] = await resp.json()
                if json_page == []:
                    break
                for item in json_page:
                    for key, value in added_fields.items():
                        item[key] = value
                json_data.extend(json_page)
                page += 1
        return json_data

    def generate_csv(
        self, file_name: str, json_list: List[Dict[str, Any]], columns_list: List
    ) -> None:
        """Write CSV file.

        Args:
            file_name (str): Name of the CSV file
            json_list (List[Dict[str, Any]]): JSON data to turn into CSV
            columns_list (List): List of columns that represent relevant fields
                                 in the JSON data
        """
        with open(Path(self.data_directory, file_name), "a+", encoding="utf-8") as file:
            csv_file = csv.DictWriter(
                file, fieldnames=columns_list, extrasaction="ignore"
            )
            csv_file.writeheader()
            for item in json_list:
                csv_file.writerow(item)
        print(f"- file saved as {Path('data', self.data_directory.name, file_name)}")

    async def get_org_repos(self) -> List[Dict[str, Any]]:
        """Create list of the organizations' repositories."""
        print("Scraping repositories")
        tasks: List[asyncio.Task[Any]] = []
        for org in self.orgs:
            url = f"https://api.github.com/orgs/{org}/repos"
            tasks.append(asyncio.create_task(self.call_api(url, organization=org)))
        return await self.load_json(tasks)

    async def create_org_repo_csv(self) -> None:
        """Write a CSV file with information about orgs' repositories."""
        # Create list of items that should appear as columns in the CSV
        table_columns: List[str] = [
            "organization",
            "name",
            "full_name",
            "stargazers_count",
            "language",
            "created_at",
            "updated_at",
            "homepage",
            "fork",
            "description",
        ]
        self.generate_csv("org_repositories.csv", self.repos, table_columns)

    async def get_repo_contributors(self) -> None:
        """Create list of contributors to the organizations' repositories."""
        print("Scraping contributors")
        json_contributors_all = []
        graph = nx.DiGraph()
        table_columns: List[str] = [
            "organization",
            "repository",
            "login",
            "contributions",
            "html_url",
            "url",
        ]
        tasks: List[asyncio.Task[Any]] = []
        for org in self.orgs:
            for repo in self.repos:
                url = f"https://api.github.com/repos/{org}/{repo['name']}/contributors"
                tasks.append(
                    asyncio.create_task(
                        self.call_api(url, organization=org, repository=repo["name"])
                    )
                )
        json_contributors_all = await self.load_json(tasks)
        self.generate_csv("contributor_list.csv", json_contributors_all, table_columns)
        for contributor in json_contributors_all:
            graph.add_node(
                contributor["repository"], organization=contributor["organization"]
            )
            graph.add_edge(
                contributor["login"],
                contributor["repository"],
                organization=contributor["organization"],
            )
        nx.write_gexf(graph, Path(self.data_directory, "contributor_network.gexf"))
        print(
            "- file saved as "
            f"{Path('data', self.data_directory.name, 'contributor_network.gexf')}"
        )

    async def get_members_repos(self) -> None:
        """Create list of all the members of an organization and their repositories."""
        print("Getting repositories of all members.")
        json_members_repos: List[Dict[str, Any]] = []
        table_columns: List[str] = [
            "organization",
            "user",
            "full_name",
            "fork",
            "stargazers_count",
            "forks_count",
            "language",
            "description",
        ]
        tasks: List[asyncio.Task[Any]] = []
        for org in self.members:
            for member in self.members[org]:
                url = f"https://api.github.com/users/{member}/repos"
                tasks.append(
                    asyncio.create_task(
                        self.call_api(url, organization=org, user=member)
                    )
                )
        json_members_repos = await self.load_json(tasks)
        self.generate_csv("members_repositories.csv", json_members_repos, table_columns)

    async def get_members_info(self) -> None:
        """Gather information about the organizations' members."""
        print("Getting user information of all members.")
        table_columns: List[str] = [
            "organization",
            "login",
            "name",
            "url",
            "type",
            "company",
            "blog",
            "location",
        ]
        tasks: List[asyncio.Task[Any]] = []
        for org in self.orgs:
            for member in self.members[org]:
                url = f"https://api.github.com/users/{member}"
                tasks.append(asyncio.create_task(self.call_api(url, organization=org)))
        json_members_info: List[Dict[str, Any]] = await self.load_json(tasks)
        self.generate_csv("members_info.csv", json_members_info, table_columns)

    async def get_starred_repos(self) -> None:
        """Create list of all the repositories starred by organizations' members."""
        print("Getting repositories starred by members.")
        json_starred_repos_all: List[Dict[str, Any]] = []
        table_columns: List[str] = [
            "organization",
            "user",
            "full_name",
            "html_url",
            "language",
            "description",
        ]
        tasks: List[asyncio.Task[Any]] = []
        for org in self.members:
            for member in self.members[org]:
                url = f"https://api.github.com/users/{member}/starred"
                tasks.append(
                    asyncio.create_task(
                        self.call_api(url, organization=org, user=member)
                    )
                )
        json_starred_repos_all = await self.load_json(tasks)
        self.generate_csv(
            "starred_repositories.csv", json_starred_repos_all, table_columns
        )

    async def generate_follower_network(self) -> None:
        """Create full or narrow follower networks of organizations' members.

        Get every user following the members of organizations (followers)
        and the users they are following themselves (following). Then generate two
        directed graphs with NetworkX. Only includes members of specified organizations
        if in narrow follower network.

        TODO: Don't create a separate narrow follower network. Instead, try to add an
              attribute to the nodes to mark them as 'narrow' so you can filter them out
              in Gephi. Will simplify this function, but double check that this works
              correctly before you remove the code for generating narrow follower
              networks
        """
        print("Generating follower networks")
        # Create graph dict and add self.members as nodes
        graph_full = nx.DiGraph()
        graph_narrow = nx.DiGraph()
        for org in self.orgs:
            for member in self.members[org]:
                graph_full.add_node(member, organization=org)
                graph_narrow.add_node(member, organization=org)

        # Get followers and following for each member and build graph
        tasks_followers: List[asyncio.Task[Any]] = []
        tasks_following: List[asyncio.Task[Any]] = []
        for org in self.members:
            for member in self.members[org]:
                url_followers = f"https://api.github.com/users/{member}/followers"
                tasks_followers.append(
                    asyncio.create_task(
                        self.call_api(url_followers, follows=member, original_org=org)
                    )
                )
                url_following = f"https://api.github.com/users/{member}/following"
                tasks_following.append(
                    asyncio.create_task(
                        self.call_api(
                            url_following, followed_by=member, original_org=org
                        )
                    )
                )
        json_followers = await self.load_json(tasks_followers)
        json_following = await self.load_json(tasks_following)
        # Build full and narrow graphs
        for follower in json_followers:
            graph_full.add_edge(
                follower["login"],
                follower["follows"],
                organization=follower["original_org"],
            )
            if follower["login"] in self.members[follower["original_org"]]:
                graph_narrow.add_edge(
                    follower["login"],
                    follower["follows"],
                    organization=follower["original_org"],
                )
        for following in json_following:
            graph_full.add_edge(
                following["followed_by"],
                following["login"],
                organization=following["original_org"],
            )
            if following["login"] in self.members[following["original_org"]]:
                graph_narrow.add_edge(
                    following["followed_by"],
                    following["login"],
                    organization=following["original_org"],
                )
        # Write graphs and save files
        nx.write_gexf(
            graph_full, Path(self.data_directory, "full-follower-network.gexf")
        )
        nx.write_gexf(
            graph_narrow, Path(self.data_directory, "narrow-follower-network.gexf")
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
        tasks: List[asyncio.Task[Any]] = []
        for org in self.members:
            for member in self.members[org]:
                url = f"https://api.github.com/users/{member}/orgs"
                tasks.append(
                    asyncio.create_task(
                        self.call_api(url, organization=org, scraped_org_member=member)
                    )
                )
        json_org_memberships = await self.load_json(tasks)
        for membership in json_org_memberships:
            graph.add_node(membership["scraped_org_member"], node_type="user")
            graph.add_edge(
                membership["scraped_org_member"],
                membership["login"],  # name of organization user is member of
                node_type="organization",
            )
        nx.write_gexf(graph, Path(self.data_directory, "membership_network.gexf"))
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
        with open(Path(Path.cwd(), "config.json"), "r", encoding="utf-8") as file:
            config = json.load(file)
            user: str = config["user_name"]
            api_token: str = config["api_token"]
            if user == "" or api_token == "":
                raise KeyError
            else:
                return user, api_token
    except (FileNotFoundError, KeyError):
        sys.exit(
            "Failed to read Github user name and/or API token. "
            "Please add them to the config.json file."
        )


def read_organizations() -> List[str]:
    """Read list of organizations from file.

    Returns:
        List[str]: List of names of organizational Github accounts
    """
    orgs: List[str] = []
    with open(Path(Path.cwd(), "organizations.csv"), "r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        for row in reader:
            orgs.append(row["github_org_name"])
    if not orgs:
        sys.exit(
            "No organizations to scrape found in organizations.csv. "
            "Please add the names of the organizations you want to scrape "
            "in the column 'github_org_name' (one name per row)."
        )
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
        help="scrape all the information listed below",
    )
    argparser.add_argument(
        "--repos",
        "-r",
        action="store_true",
        dest="create_org_repo_csv",
        help="scrape the organizations' repositories (CSV)",
    )
    argparser.add_argument(
        "--contributors",
        "-c",
        action="store_true",
        dest="get_repo_contributors",
        help="scrape contributors of the organizations' repositories (CSV and GEXF)",
    )
    argparser.add_argument(
        "--member_repos",
        "-mr",
        action="store_true",
        dest="get_members_repos",
        help="scrape all repositories owned by the members of the organizations (CSV)",
    )
    argparser.add_argument(
        "--member_infos",
        "-mi",
        action="store_true",
        dest="get_members_info",
        help="scrape information about each member of the organizations (CSV)",
    )
    argparser.add_argument(
        "--starred",
        "-s",
        action="store_true",
        dest="get_starred_repos",
        help="scrape all repositories starred by members of the organizations (CSV)",
    )
    argparser.add_argument(
        "--followers",
        "-f",
        action="store_true",
        dest="generate_follower_network",
        help="generate a follower network. Creates full and narrow network graph, the "
        "latter only shows how scraped organizations are networked among each "
        "other (two GEXF files)",
    )
    argparser.add_argument(
        "--memberships",
        "-m",
        action="store_true",
        dest="generate_memberships_network",
        help="scrape all organizational memberships of org members (GEXF)",
    )
    args: Dict[str, bool] = vars(argparser.parse_args())
    return args


async def main() -> None:
    """Set up GithubScraper object."""
    args: Dict[str, bool] = parse_args()
    if not any(args.values()):
        sys.exit(
            "You need to provide at least one argument. "
            "For usage, call: github_scraper -h"
        )
    user, api_token = read_config()
    organizations = read_organizations()
    # To avoid unnecessary API calls, only get org members and repos if needed
    require_members = [
        "get_members_repos",
        "get_members_info",
        "get_starred_repos",
        "generate_follower_network",
        "generate_memberships_network",
    ]
    require_repos = ["create_org_repo_csv", "get_repo_contributors"]
    # Start aiohttp session
    auth = aiohttp.BasicAuth(user, api_token)
    async with aiohttp.ClientSession(auth=auth) as session:
        github_scraper = GithubScraper(organizations, session)
        # If --all was provided, simply run everything
        if args["all"]:
            github_scraper.members = await github_scraper.get_members()
            github_scraper.repos = await github_scraper.get_org_repos()
            for arg in args:
                if arg != "all":
                    await getattr(github_scraper, arg)()
        else:
            # Check args provided, get members/repos if necessary, call related methods
            called_args = [arg for arg, value in args.items() if value]
            if any(arg for arg in called_args if arg in require_members):
                github_scraper.members = await github_scraper.get_members()
            if any(arg for arg in called_args if arg in require_repos):
                github_scraper.repos = await github_scraper.get_org_repos()
            for arg in called_args:
                await getattr(github_scraper, arg)()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
