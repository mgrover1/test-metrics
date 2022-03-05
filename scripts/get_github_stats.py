#!/usr/bin/env python
import click
import pandas as pd

from utils.target_repos import TargetRepos
from utils import github_queries as gq


@click.command()
@click.option(
    '-t',
    '--token',
    help='GitHub personal access token for GraphQL access',
)
def main(token):
    repos = TargetRepos()

    print('Downloading general repository information from GitHub...')
    repos_df = gq.get_all_repos_info(repos=repos, token=token)
    repos_df.to_csv('data/github_repos.csv', index=False)

    commits_df = pd.DataFrame()
    dfs = []
    print('Downloading commit histories for each repository...')
    for repo in repos.values():
        owner = repo['org']
        name = repo['repo']
        print(f'  {owner}/{name}...', end='', flush=True)
        df = gq.get_repo_commits(owner=owner, name=name, token=token)
        print(f'  ({len(df)} commits)')
        dfs.append(df)
    commits_df = pd.concat(dfs, ignore_index=True)
    commits_df.to_csv('data/github_commits.csv', index=False)

    dfs = []
    print('Downloading issue statistics for each repository...')
    for repo in repos.values():
        owner = repo['org']
        name = repo['repo']
        print(f'  {owner}/{name}...', end='', flush=True)
        df = gq.get_repo_issues(owner=owner, name=name, token=token)
        print(f'  ({len(df)} issues)')
        dfs.append(df)
    issues_df = pd.concat(dfs, ignore_index=True)
    issues_df.to_csv('data/github_issues.csv', index=False)

    print('Done.')


if __name__ == '__main__':
    main(auto_envvar_prefix='GITHUB')