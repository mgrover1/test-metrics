from collections import defaultdict

import requests
import pandas as pd


def get_all_repos_info(repos={}, token=None):
    if len(repos) == 0:
        return None

    repo_queries = []
    for key, val in repos.items():
        pkg = key.replace('-', '_')
        owner = val['org']
        name = val['repo']

        repo_queries.append(
            f'  {pkg}: repository(owner: "{owner}", name: "{name}") {{ ...repoInfo }}'
        )
    queries = '\n'.join(repo_queries)

    query = f"""
fragment repoInfo on Repository {{
  forkCount
  latestRelease {{
    tag {{
      name
    }}
  }}
  stargazerCount
  watchers {{
    totalCount
  }}
}}
{{
{queries}
}}
"""

    url = 'https://api.github.com/graphql'
    json = {'query': query}
    headers = {'Authorization': f'bearer {token}'}
    response = requests.post(url, json=json, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(f'Failed to read project data [{response.status_code}]')
    response_data = response.json()

    data = defaultdict(list)
    for pkg in response_data['data']:
        data['package'].append(pkg)
        data['forks'].append(response_data['data'][pkg]['forkCount'])
        if response_data['data'][pkg]['latestRelease']:
            rls = response_data['data'][pkg]['latestRelease']['tag']['name']
        else:
            rls = None
        data['release'].append(rls)
        data['stargazers'].append(response_data['data'][pkg]['stargazerCount'])
        data['watchers'].append(response_data['data'][pkg]['watchers']['totalCount'])

    df = pd.DataFrame.from_dict(data)

    return df.astype(dtype={'forks': 'int64', 'stargazers': 'int64', 'watchers': 'int64'})


def get_repo_commits(owner=None, name=None, token=None):
    if owner is None or name is None:
        return None

    url = 'https://api.github.com/graphql'
    headers = {'Authorization': f'bearer {token}'}

    after = None
    has_next_page = True
    data = defaultdict(list)
    while has_next_page:
        after_str = '' if after is None else f', after: "{after}"'
        query = f"""
query {{
  repository(owner: "{owner}", name: "{name}") {{
    defaultBranchRef {{
      target {{
        ... on Commit {{
          history(first: 100{after_str}) {{
            pageInfo {{
              endCursor
              hasNextPage
            }}
            edges {{
              node {{
                additions
                committedDate
                deletions
                author {{
                  user {{
                    login
                  }}
                }}
              }}
            }}
          }}
        }}
      }}
    }}
  }}
}}
"""

        json = {'query': query}
        response = requests.post(url, json=json, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f'Failed to read project data [{response.status}]')
        response_json = response.json()
        default_branch_data = response_json['data']['repository']['defaultBranchRef']
        history_data = default_branch_data['target']['history']

        after = history_data['pageInfo']['endCursor']
        has_next_page = history_data['pageInfo']['hasNextPage']

        for node in history_data['edges']:
            data['package'].append(name)
            data['additions'].append(node['node']['additions'])
            data['deletions'].append(node['node']['deletions'])
            data['date'].append(node['node']['committedDate'])
            user = node['node']['author']['user']
            author = user['login'] if user else None
            data['author'].append(author)

    df = pd.DataFrame.from_dict(data)

    return df.astype(dtype={'additions': 'int64', 'deletions': 'int64'})


def get_repo_issues(owner=None, name=None, token=None):
    if owner is None or name is None:
        return None

    url = 'https://api.github.com/graphql'
    headers = {'Authorization': f'bearer {token}'}

    data = defaultdict(list)
    after = None
    has_next_page = True
    while has_next_page:
        after_str = '' if after is None else f', after: "{after}"'
        query = f"""
query {{
  repository(owner: "{owner}", name: "{name}") {{
    issues(first: 100{after_str}) {{
      pageInfo {{
        endCursor
        hasNextPage
      }}
      edges {{
        node {{
          number
          createdAt
          closedAt
          author {{
            login
          }}
        }}
      }}
    }}
  }}
}}
"""

        json = {'query': query}
        response = requests.post(url, json=json, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f'Failed to read project data [{response.status}]')
        response_data = response.json()
        issue_data = response_data['data']['repository']['issues']

        after = issue_data['pageInfo']['endCursor']
        has_next_page = issue_data['pageInfo']['hasNextPage']

        for node in issue_data['edges']:
            data['package'].append(name)
            data['number'].append(node['node']['number'])
            data['created'].append(node['node']['createdAt'])
            data['closed'].append(node['node']['closedAt'])
            data['author'].append(node['node']['author']['login'])

    return pd.DataFrame(data)