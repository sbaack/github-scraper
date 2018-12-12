import requests
import sys

# Usage:
#
#   Parses github orgs from ORG_DATA_URL.
#
#     python parse_codeforall.py [ <tag> ]
#
#     Example: python parse_codeforall.py
#     Example: python parse_codeforall.py "Code for America"

ORG_DATA_URL = 'https://raw.githubusercontent.com/Code-for-All/codeforall.org/gh-pages/_data/organizations.json'

def get_org_slugs_by_tag(tag=''):
    orgs = []
    org_slugs = []
    r = requests.get(ORG_DATA_URL)
    if r.status_code != 200:
        print("Error. Quitting...")
        raise SystemExit
    data = r.json()
    if tag:
        orgs = [o for o in data if tag in o['tags']]
    else:
        orgs = [o for o in data]

    for o in orgs:
        slug = get_github_org_slug(o)
        if slug and slug not in org_slugs:
            org_slugs.append(slug)

    return org_slugs

def print_org_slugs_by_tag(tag=''):
    org_slugs = get_org_slugs_by_tag(tag)
    for s in org_slugs:
            print(s)

def get_github_org_slug(org):
    if 'projects_list_url' in org:
        url = org['projects_list_url']
        if 'github.com' in url:
            return extract_org_slug(url)
    return ''

def extract_org_slug(url):
    return url.split('/')[-1]

if len(sys.argv) > 1:
    tag = sys.argv[1]
else:
    tag = None

print_org_slugs_by_tag(tag)
