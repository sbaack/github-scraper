"""Scrape GitHub data for organizational accounts."""

import csv
import json
import time
from sys import exit
from typing import List

import networkx as nx
import requests


def select_options():
    """Show menu that lets user select scraping option(s).

    Getting started by loading GitHub user name and API token, reading
    list of organizations and letting user choose an operation.
    """
    global username, api_token
    # Try to read username and api_token
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            username = config['username']
            api_token = config['api_token']
            if username == "" or api_token == "":
                exit(1)
            else:
                print(f"User name: {username}")
                print(f"Api token: {api_token}")
    except (FileNotFoundError, KeyError):
        print("Failed to read user name and password in config.jon file.")
        exit(1)
    # Read list of organizations from file
    print("\nReading list of organizations from file.\n")
    org_list = []
    with open('organizations.txt', 'r') as f:
        for line in f:
            # Using rstrip to remove the newline escape sequences
            org_list.append(line.rstrip('\n'))
    print("Will scrape data from the following organizations:", *org_list)
    # Let user specify an operation
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
        "Choose options. To select all, type 'All'. To select multiple, use comma separated list.\n> "
    )
    operations = operations.lower()
    if operations == 'all':
        operations = "1, 2, 3, 4, 5, 6, 7, 8"
    operations_input = operations.split(', ')
    operations_dict = {
        1: get_repos,
        2: get_contributors,
        3: get_members_repos,
        4: get_members_info,
        5: get_starred_repos,
        6: generate_follower_network,
        7: generate_follower_network,
        8: generate_memberships
    }
    for operation in operations_input:
        if int(operation) == 6:
            operations_dict[int(operation)](org_list, network_type="full")
        elif int(operation) == 7:
            operations_dict[int(operation)](org_list, network_type="narrow")
        else:
            operations_dict[int(operation)](org_list)


def load_json(url: str, memberscrape: bool = False):
    """Load json file using requests.

    Iterates over the pages of the API and returns a list of dicts.
    """
    # TODO: Add error handling if request fails (e.g. if repo was not found)
    if memberscrape:
        r = requests.get(
            url,
            auth=(username, api_token)
        )
        jsonData = json.loads(r.text)
        return jsonData
    else:
        page = 1
        jsonList = []
        page_not_empty = True
        while page_not_empty:
            r = requests.get(
                f"{url}&page={str(page)}",
                auth=(username, api_token)
            )
            jsonData = json.loads(r.text)
            if jsonData == []:
                page_not_empty = False
            else:
                jsonList.extend(jsonData)
                page += 1
        return jsonList


def generate_csv(type: str, json_list: List, columns_list: List):
    """Write CSV file."""
    with open(
        f"data/{type}_{time.strftime('%Y-%m-%d_%H:%M:%S')}.csv",
        'a+'
    ) as f:
        csv_file = csv.DictWriter(
            f,
            fieldnames=columns_list,
            extrasaction="ignore"
        )
        csv_file.writeheader()
        for item in json_list:
            csv_file.writerow(item)
    print(
        f"\nCSV file saved as data/{type}_{time.strftime('%Y-%m-%d_%H:%M:%S')}.csv"
    )


def get_repos(org_list: List):
    """Create list of the organizations' repositories."""
    jsonRepos = []
    for org in org_list:
        print(f"\nScraping repositories of {org}")
        jsonRepo = load_json(
            f"https://api.github.com/orgs/{org}/repos?per_page=100"
        )
        for repo in jsonRepo:
            # Add field for org to make CSV file more useful
            repo['organization'] = org
            jsonRepos.append(repo)
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
    generate_csv("repo-list", jsonRepos, columns_list)


def get_contributors(org_list: List):
    """Create list of contributors to the organizations' repositories."""
    print("\nCreating list of contributors.")
    jsonContributor_list = []
    graph = nx.DiGraph()
    columns_list = [
        'organization',
        'repository',
        'login',
        'contributions',
        'html_url',
        'url'
    ]
    for org in org_list:
        print(f"\nScraping contributors of {org}")
        jsonRepo = load_json(
            f"https://api.github.com/orgs/{org}/repos?per_page=100"
        )
        for repo in jsonRepo:
            try:
                print(f"Getting contributors of {repo['name']}")
                # First, add repo as a node to the graph
                graph.add_node(repo['name'], organization=org)
                # Then get a list of contributors
                jsonContributors = load_json(
                    f"https://api.github.com/repos/{org}/{repo['name']}/contributors?per_page=100"
                )
                for contributor in jsonContributors:
                    # Add each contributor as an edge to the graph
                    graph.add_edge(
                        contributor['login'],
                        repo['name'],
                        organization=org
                    )
                    # Prepare CSV and add fields to make it more usable
                    contributor["organization"] = org
                    contributor["repository"] = repo["name"]
                    jsonContributor_list.append(contributor)
            except json.decoder.JSONDecodeError:
                # If repository is empty, inform user and pass
                print(
                    f"Repository '{repo['name']}' appears to be empty."
                )
                pass
    generate_csv("contributor-list", jsonContributor_list, columns_list)
    # TODO: Use variable for name of the file
    nx.write_gexf(
        graph,
        f"data/contributor-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
    )
    print(
        f"\nSaved graph file: data/contributor-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
    )


def get_members_repos(org_list: List):
    """Create list of all the members of an organization and their repositories."""
    print("\nGetting repositories of all members.")
    jsonMembersRepo_list = []
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
    for org in org_list:
        print(f"\nGetting members of {org}")
        jsonMembers = load_json(
            f"https://api.github.com/orgs/{org}/members?per_page=100"
        )
        for member in jsonMembers:
            print(f"Getting repositories of {member['login']}")
            jsonMembersRepos = load_json(
                f"https://api.github.com/users/{member['login']}/repos?per_page=100"
            )
            for repo in jsonMembersRepos:
                # Add fields to make CSV file more usable
                repo['organization'] = org
                repo['user'] = member['login']
                jsonMembersRepo_list.append(repo)
    generate_csv("members-list", jsonMembersRepo_list, columns_list)


def get_members_info(org_list: List):
    """Gather information about the organizations' members."""
    print("\nGetting user information of all members.")
    jsonMembersInfo_list = []
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
    for org in org_list:
        print(f"\nGetting members of {org}")
        jsonMembers = load_json(
            f"https://api.github.com/orgs/{org}/members?per_page=100"
        )
        for member in jsonMembers:
            print(f"Getting user information for {member['login']}")
            jsonMember = load_json(
                f"https://api.github.com/users/{member['login']}?per_page=100",
                memberscrape=True
            )
            # Add field to make CSV file more usable
            jsonMember["organization"] = org
            jsonMembersInfo_list.append(jsonMember)
    generate_csv("members-info", jsonMembersInfo_list, columns_list)


def get_starred_repos(org_list: List):
    """Create list of all the repositories starred by organizations' members."""
    print("\nGetting repositories starred by members.")
    jsonMembersStarred_list = []
    columns_list = [
        'organization',
        'user',
        'full_name',
        'html_url',
        'language',
        'description'
    ]
    for org in org_list:
        print(f"\nGetting members of {org}")
        jsonMembers = load_json(
            f"https://api.github.com/orgs/{org}/members?per_page=100"
        )
        for member in jsonMembers:
            print(f"Getting starred repositories of {member['login']}")
            jsonStarred = load_json(
                f"https://api.github.com/users/{member['login']}/starred?per_page=100"
            )
            for repo in jsonStarred:
                repo['organization'] = org
                repo['user'] = member['login']
                jsonMembersStarred_list.append(repo)
    generate_csv("starred-list", jsonMembersStarred_list, columns_list)


def generate_follower_network(org_list: List, network_type: str = ""):
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
        for org in org_list:
            print(f"\nGetting members of specified organizations to filter network...")
            jsonMembers = load_json(
                f"https://api.github.com/orgs/{org}/members?per_page=100"
            )
            for member in jsonMembers:
                members_list.append(member['login'])

    graph = nx.DiGraph()
    for org in org_list:
        print(f"\nGetting members of {org}")
        jsonMembers = load_json(
            f"https://api.github.com/orgs/{org}/members?per_page=100"
        )
        for member in jsonMembers:
            jsonMembersFollowers = load_json(
                f"https://api.github.com/users/{member['login']}/followers?per_page=100"
            )
            jsonMembersFollowing = load_json(
                f"https://api.github.com/users/{member['login']}/following?per_page=100"
            )
            print(f"Getting follower network of {member['login']}")
            graph.add_node(member['login'], organization=org)
            if network_type == "full":
                for follower in jsonMembersFollowers:
                    graph.add_edge(
                        follower['login'],
                        member['login'],
                        organization=org
                    )
                for following in jsonMembersFollowing:
                    graph.add_edge(
                        member['login'],
                        following['login'],
                        organization=org
                    )
            else:
                # Generate narrow network excluding non-members
                for follower in jsonMembersFollowers:
                    if follower['login'] in members_list:
                        graph.add_edge(
                            follower['login'],
                            member['login'],
                            organization=org
                        )
                for following in jsonMembersFollowing:
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
        f"\nSaved graph file: data/{network_type}-follower-network_{time.strftime('%Y-%m-%d_%H:%M:%S')}.gexf"
    )


def generate_memberships(org_list: List):
    """Take all the members of the organizations and generate a directed graph.

    This shows creates a network with the organizational memberships.
    """
    print("\nGenerating network of memberships.")
    graph = nx.DiGraph()
    for org in org_list:
        jsonMembers = load_json(
            f"https://api.github.com/orgs/{org}/members?per_page=100"
        )
        for member in jsonMembers:
            print(f"Getting membership of {member['login']}")
            graph.add_node(member['login'], node_type='user')
            jsonMemberships = load_json(
                f"https://api.github.com/users/{member['login']}/orgs?per_page=100"
            )
            for organization in jsonMemberships:
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
    select_options()
