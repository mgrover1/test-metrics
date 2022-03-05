#!/usr/bin/env python
from datetime import datetime, timedelta
from pathlib import Path

from bokeh.io import output_file, save
from bokeh.models import HoverTool
from bokeh.models.formatters import DatetimeTickFormatter, PrintfTickFormatter
from bokeh.palettes import Blues4
from bokeh.plotting import figure, reset_output
import pandas as pd
import requests

from utilities.target_repos import TargetRepos

ROOT_DIR = Path(__file__).parent.parent
INTERNAL_AUTHORS = set(['rcjackson', 'rcjackson', 'rcjackson', 'scollis', 'mgrover1', 'jhemedin', 'AdamTheisen'])


def _make_stacked_bar_plot(
    df: pd.DataFrame,
    filename: str,
    title: str,
    sourcename: str,
) -> None:
    names = list(df.columns)
    if len(names) == 0:
        return

    reset_output()
    output_file(ROOT_DIR / filename)

    dtformatter = DatetimeTickFormatter(
        days='%d %b %Y',
        months='%b %Y',
    )
    yformatter = PrintfTickFormatter(format='%6.1u')
    tooltips = [(sourcename, '@$name'), ('Date', '@month{%b %Y}')]
    if len(names) > 1:
        tooltips.insert(0, ('Source', '$name'))
    tools = [HoverTool(tooltips=tooltips, formatters={'@month': 'datetime'})]

    x_dt = timedelta(days=17)
    x_min = df.index.min().to_timestamp() - x_dt
    x_max = df.index.max().to_timestamp() + x_dt

    p = figure(
        title=title,
        height=200,
        width=800,
        toolbar_location='right',
        tools=tools,
        x_range=(x_min, x_max),
        y_range=(0, df.sum(axis=1).max()*1.1),
        sizing_mode='scale_width',
    )
    extra_kwargs = {}
    if len(names) > 1:
        extra_kwargs['legend_label'] = names
    p.vbar_stack(
        names,
        x='month',
        color=Blues4[:len(names)],
        width=timedelta(days=25).total_seconds() * 1000,
        source=df,
        **extra_kwargs,
    )
    p.xaxis.formatter = dtformatter
    p.yaxis.formatter = yformatter
    p.title.text_font_size = '1rem'
    if len(names) > 1:
        p.legend.location = 'top_left'
    save(p)


def get_downloads_data() -> pd.DataFrame:
    df_pypi = pd.read_csv(ROOT_DIR / 'data/pypi_stats.csv', index_col='month')
    df_pypi.index = pd.to_datetime(df_pypi.index).to_period('M')

    df_conda = pd.read_csv(ROOT_DIR / 'data/conda_stats.csv', index_col='month')
    df_conda.index = pd.to_datetime(df_conda.index).to_period('M')

    pkgs = set(df_pypi.columns).union(df_conda.columns)
    dfs = {}
    for pkg in pkgs:
        df = pd.DataFrame()
        df.index = pd.period_range(
            start='2019-01',
            periods=0,
            freq='M',
            name='month',
        )
        include_df = False
        if pkg in df_pypi and df_pypi[pkg].sum() > 0:
            df['PyPI'] = df_pypi[pkg]
            df['PyPI'] = df['PyPI'].fillna(0).astype('int64')
            include_df = True
        if pkg in df_conda and df_conda[pkg].sum() > 0:
            df['Conda'] = df_conda[pkg]
            df['Conda'] = df['Conda'].fillna(0).astype('int64')
            include_df = True
        if include_df:
            dfs[pkg] = df

    return dfs


def get_repo_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT_DIR / 'data/github_repos.csv')
    df.package = df.package.apply(lambda x: x.replace('_', '-'))
    return df


def get_commits_data() -> pd.DataFrame:
    def author_type(author):
        if author in INTERNAL_AUTHORS:
            return 'Internal'
        elif '[bot]' in str(author):
            return None
        else:
            return 'External'

    df = pd.read_csv(ROOT_DIR / 'data/github_commits.csv', index_col='date', parse_dates=True) \
           .sort_index() \
           .tz_localize(None)
    df['changes'] = df.additions + df.deletions
    df['author_type'] = df.author.apply(author_type)
    df = df.drop(columns=['additions', 'deletions'])
    return df


def get_issue_data() -> pd.DataFrame:
    df = pd.read_csv(ROOT_DIR / 'data/github_issues.csv')
    df.created = pd.to_datetime(df.created).dt.tz_localize(None)
    df.closed = pd.to_datetime(df.closed).dt.tz_localize(None)
    df['is_open'] = df.closed.apply(lambda x: pd.isnull(x))
    return df


def make_downloads_images(dfs: dict[pd.DataFrame]):
    for pkg in dfs:
        df = dfs[pkg]
        filename = f'images/metrics/{pkg}-downloads.html'
        title = 'Package Downloads'
        _make_stacked_bar_plot(df, filename, title, 'Downloads')


def make_commit_images(df_c: pd.DataFrame):
    df_c = df_c.drop(columns='author').dropna()
    idx = pd.MultiIndex.from_product([
        pd.period_range(start=df_c.index.min(), end=df_c.index.max(), freq='M'),
        df_c.package.unique(),
        df_c.author_type.unique(),
    ], names=['month', 'package', 'author_type'])
    df_c = df_c.groupby([df_c.index.to_period('M'), 'package', 'author_type']) \
               .sum() \
               .reindex(idx, fill_value=0) \
               .reset_index(['package', 'author_type'])

    for pkg in df_c.package.unique():
        df = df_c.loc[df_c.package == pkg] \
                 .drop(columns='package') \
                 .reset_index() \
                 .pivot(index='month', columns='author_type', values='changes') \
                 .astype('int64')
        filename = f'images/metrics/{pkg}-commits.html'
        title = 'Repository Changes (Additions + Deletions)'
        _make_stacked_bar_plot(df, filename, title, 'Changes')


def make_contributor_images(df_c: pd.DataFrame):
    def cumsum_unique_authors(data):
        data['authors'] = data['authors'].cumsum().map(set).map(len)
        return data

    df_c = df_c.drop(columns='changes').dropna()
    idx = pd.MultiIndex.from_product([
        pd.period_range(start=df_c.index.min(), end=df_c.index.max(), freq='M'),
        df_c.package.unique(),
        df_c.author_type.unique(),
    ], names=['month', 'package', 'author_type'])
    df_c = df_c.groupby([df_c.index.to_period('M'), 'package', 'author_type']) \
               .agg(list) \
               .rename(columns={'author': 'authors'}) \
               .reindex(idx, fill_value=[]) \
               .reset_index(['package', 'author_type']) \
               .groupby(['package', 'author_type']) \
               .apply(cumsum_unique_authors)

    for pkg in df_c.package.unique():
        df = df_c.loc[df_c.package == pkg] \
                 .drop(columns='package') \
                 .reset_index() \
                 .pivot(index='month', columns='author_type', values='authors') \
                 .astype('int64')
        filename = f'images/metrics/{pkg}-contributors.html'
        title = 'Number of Contributors'
        _make_stacked_bar_plot(df, filename, title, 'Contributors')


def make_burndown_images(df_i: pd.DataFrame):
    for pkg in df_i.package.unique():
        df = pd.DataFrame(columns=['nopen'])
        df_i_p = df_i.loc[df_i.package == pkg]
        start_time = df_i.created.min()
        end_time = datetime.today()
        for month in pd.date_range(start=start_time, end=end_time, freq='M'):
            _df = df_i_p.loc[(df_i_p.created <= month) & (df_i_p.package == pkg)]
            _df = _df.loc[(_df.is_open) | (_df.closed > month)]
            df.loc[month.to_period('M')] = _df.number.count()
        df.index.name = 'month'

        filename = f'images/metrics/{pkg}-burndown.html'
        title = 'Open Issues'
        _make_stacked_bar_plot(df, filename, title, 'Issues')


def make_packages_markdown():
    packages_md = """# Package Metrics
Below are some of the metrics related to activity on repositories that Xdev owns
and package downloads for repositories that are published packaged on PyPI or
Conda Forge.  These metrics are updated periodically, so check back later for
new information.  (*Note that Conda download statistics can be months out of
date, so it is likely that download numbers for the current and last months will
be inaccurate.*)
"""

    repos = XdevRepos()
    repo_data = get_repo_data()
    packages = repo_data.package.to_list()

    dl_dfs = get_downloads_data()
    make_downloads_images(dl_dfs)

    co_df = get_commits_data()
    make_commit_images(co_df)
    make_contributor_images(co_df)

    is_df = get_issue_data()
    make_burndown_images(is_df)

    for pkg in packages:
        resp = requests.get(f'https://pypi.org/pypi/{pkg}/json')
        info = resp.json()['info'] if resp.status_code == 200 else {}

        summary = f"> {info['summary']}" if 'summary' in info else ''
        url = f"https://github.com/{repos[pkg]['org']}/{repos[pkg]['repo']}"

        this_time = datetime.now()
        this_year = this_time.year
        last_year = this_year - 1

        if pkg.lower() in dl_dfs:
            df = dl_dfs[pkg.lower()]
            dls_this_year = df[df.index.year == this_year].sum().sum()
            dls_last_year = df[df.index.year == last_year].sum().sum()
        else:
            dls_this_year = 0
            dls_last_year = 0

        dl_str = ''
        if dls_last_year > 0:
            dls = dls_last_year
            yr = last_year
            dl_str += f'In {yr}, there were **{dls} downloads**. '
        if dls_this_year > 0:
            dls = dls_this_year
            yr = this_year
            dl_str += f'Currently, there have been **{dls} downloads** so far in {yr}.'

        pkg_data = repo_data[repo_data.package == pkg]
        watchers = int(pkg_data['watchers'].item())
        stargazers = int(pkg_data['stargazers'].item())
        release = str(pkg_data['release'].item())
        if release == 'nan':
            release_str = ''
        else:
            release_str = f'The most recent release is tagged at **{release}**.'

        packages_md += f"""
## {pkg}
{summary}
The `{pkg}` [repository]({url}) has **{watchers} Watchers** and **{stargazers} Stargazers**.
{dl_str}
{release_str}
:::{{raw}} html
---
file: ../images/metrics/{pkg.lower()}-downloads.html
---
:::
:::{{raw}} html
---
file: ../images/metrics/{pkg.lower()}-commits.html
---
:::
:::{{raw}} html
---
file: ../images/metrics/{pkg.lower()}-contributors.html
---
:::
:::{{raw}} html
---
file: ../images/metrics/{pkg.lower()}-burndown.html
---
:::
"""

    with open(ROOT_DIR / 'stats/packages.md', 'w') as f:
        f.write(packages_md)


if __name__ == '__main__':
    make_packages_markdown()