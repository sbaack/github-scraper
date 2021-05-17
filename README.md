# GitHub scraper

This tool focuses on scraping information from _[organizational Github accounts](https://developer.github.com/v3/orgs/)_, which means that it only takes a list or organizations as input, not normal user accounts. It generates CSV spreadsheets or [GEXF](https://gephi.org/gexf/format/) files to be used in network analysis software like [Gephi](https://gephi.github.io/).

The scraper offers the following options:

1. Scrape the organizations' repositories (CSV).
2. Scrape contributors of the organizations' repositories and return results as a spreadsheet and a directed graph (CSV and GEXF).
3. Scrape all repositories owned by the members of the organizations (CSV).
4. Scrape information about each member of the organizations (CSV).
5. Scrape all repositories starred by the members of the organizations (CSV).
6. Scrape followers and followings of the organizations' member (i.e. people who follow them as well as people they are following) and generated a network (directed graph). Creates a full and a narrow network, the latter only shows how scraped organizations are networked among each other (two GEXF files).
7. Scrape all organizational memberships to graph membership structures (GEXF).

I originally wrote this scraper in 2015 for my dissertation about civic tech and data journalism. You can find the data I scraped and my analysis [here](https://sbaack.com/blog/scraping-the-global-civic-tech-community-on-github-part-2.html). If you're interested, my final dissertation is available [here](http://hdl.handle.net/11370/4c94668a-c25c-43cb-9b36-5d54e3ff3c2e).

## How to use

1. Clone this repository: `clone https://github.com/sbaack/github-scraper`
2. Install necessary dependencies (preferably in a [virtual environment](https://docs.python.org/3/tutorial/venv.html)): `pip install -r requirements.txt`. A `requirements.in` file for [pip-tools](https://github.com/jazzband/pip-tools) is also provided.
3. Open `config.json` and add your GitHub user name and your [personal access token](https://github.com/settings/tokens) to access the GitHub API.
4. Open `organizations.csv` and add the user account names of the organizations you want to scrape in the column *github_org_name*. For example, if you want to scrape [mySociety](https://github.com/mysociety), [Open Knowledge](https://github.com/okfn), and [Ushahidi](https://github.com/ushahidi), your file will look like this:

| github_org_name |
|:----------------|
| mysociety       |
| okfn            |
| ushahidi        |

Note that you can you add as many columns with additional information as you like, this scraper will ignore them.

5. Start the scraper with `python -m github_scaper` and choose an option. You can perform several scrapes in one run by entering several numbers separated by commas (, ). Alternatively, just enter 'all' to run everything. The results will be stored in the `data` subfolder.
