# GitHub scraper

This tool focuses on scraping information from _[organizational Github accounts](https://developer.github.com/v3/orgs/)_, which means that it only takes a list of organizations as input, not normal user accounts. It generates CSV spreadsheets or [GEXF](https://gephi.org/gexf/format/) files to be used in network analysis software like [Gephi](https://gephi.github.io/).

The scraper offers the following options:

```
usage: github_scraper.py [-h] [--all] [--repos] [--contributors] [--member_repos] [--member_infos] [--starred] [--followers]
                         [--memberships]

Scrape organizational accounts on Github.

optional arguments:
  -h, --help           show this help message and exit
  --all, -a            scrape all the information listed below
  --repos, -r          scrape the organizations' repositories (CSV)
  --contributors, -c   scrape contributors of the organizations' repositories (CSV and GEXF)
  --member_repos, -mr  scrape all repositories owned by the members of the organizations (CSV)
  --member_infos, -mi  scrape information about each member of the organizations (CSV)
  --starred, -s        scrape all repositories starred by the members of the organizations (CSV)
  --followers, -f      generate a follower network. Creates full and narrow network graph, the latter only shows how scraped
                       organizations are networked among each other (two GEXF files)
  --memberships, -m    scrape all organizational memberships of org members (GEXF)
```

I originally wrote this scraper in 2015 for my dissertation about civic tech and data journalism. You can find the data I scraped and my analysis [here](https://sbaack.com/blog/scraping-the-global-civic-tech-community-on-github-part-2.html). If you're interested, my final dissertation is available [here](https://research.rug.nl/en/publications/knowing-what-counts-how-journalists-and-civic-technologists-use-a).

## Setup

You need Python 3.9+.

```bash
# Clone this repository
git clone https://github.com/sbaack/github-scraper.git
# Create virtualenv with your preferred tool, for example:
cd github-scraper
python -m venv github-scraper_venv && source github-scraper_venv/bin/activate
# Install necessary dependencies
python -m pip install -r requirements.txt
```

Next, you need to add information to two configuration files. First, add your GitHub user name and your [personal access token](https://github.com/settings/tokens) to access the GitHub API in the `config.json` file. Second, add the Github account names of the organizations you want to scrape to the `organizations.csv` spreadsheet in the column *github_org_name*. For example, if you want to scrape [mySociety](https://github.com/mysociety), [Open Knowledge](https://github.com/okfn), and [Ushahidi](https://github.com/ushahidi), your file will look like this:

| github_org_name |
|:----------------|
| mysociety       |
| okfn            |
| ushahidi        |

Note that you can you add as many columns with additional information as you like, this scraper will only read the *github_org_name* column.

# How to use

Start the scraper with the desired options listed above. Some examples:

```bash
# Scrape everything this scraper provides
python -m github_scraper --all
# Scrape organizations' repos and generate follower networks
python -m github_scraper --repos --followers  # OR use the shortcuts: python -m github_scraper -r -f
# Only scrape starred repositories
python -m github_scraper --starred  # OR github_scraper -s
```

The results will be stored in the `data` subfolder, where each scrape creates it's own directory named according to the date (in the form of YEAR-MONTH-DAY_HOUR-MINUTE-SECOND).
