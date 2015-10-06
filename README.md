# GitHub scraper

This repo contains a GitHub scraper I wrote for my research project on civic hacking. At the moment it is very much focused on *organizations* and their members, i.e. it only takes a list or organizations as its input, not normal user accounts. It generates CSV spreadsheets or [GEXF](http://gexf.net/format/) files to be used in network analysis software like [Gephi](https://gephi.github.io/). I tested it with Python 2.7.10 and 3.5.0, but I recommend using Python 3.

The scraper can do the following:

1. Get a list of the organizations' repositories (CSV).
2. Get all contributors of the organizations' repositories as a spreadsheet and as a directed graph (CSV and GEXF).
3. Get a list of the repositories of all the members of the organizations (CSV).
4. Get information for each member of the organizations (CSV).
5. Get a list of all the repositories starred by the members of the organizations (CSV).
6. Generate a 'full' follower network. This will take all the members of the organizations and collect all their followers and all the users they are following. Will create a directed graph (GEXF).
7. Generate a 'narrow' follower network. Works like 6 but only collects connections between the members of the organizations scraped by the user (GEXF).
8. Generate a directed graph illustrating the membership structures (GEXF).

## How to use

1. Open `config.json` and add your GitHub user name and your [personal access token](https://github.com/settings/tokens) to access the GitHub API.
2. Open `organizations.txt` and add the user account names of the organizations you want to scrape -- one organization per line! For example, if you want to scrape [mySociety](https://github.com/mysociety), [Open Knowledge](https://github.com/okfn), and [Ushahidi](https://github.com/ushahidi), your list will look like this:

```
mysociety
okfn
ushahidi
```

3. Start the scraper with `python github_scaper.py` and choose an option. You can perform several scrapes in one run by entering several numbers separated by commas (, ). The results will be stored in the `data` subfolder.

If you cannot run the script, required packages might be missing. Install via `[sudo] pip install -r requirements.txt`.