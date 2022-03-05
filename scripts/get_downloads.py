#!/usr/bin/env python
from datetime import datetime
from pathlib import Path

import click
from dateutil.relativedelta import relativedelta
import pandas as pd

from utilities import download_stats
from utilities.target_repos import TargetRepos


def update_dataframe(df1, df2):
    """Update df1 with the contents of df2
    This operation:
    - returns df1 if df2 is None,
    - adds new columns in df1 (initialized to 0), if columns in
      df2 exist that are not already in df1,
    - overwrites rows in df1 with rows from df2, or adds rows
      in df1 from df2 if the year-month index doesn't exist
    """
    if df2 is None:
        return df1

    for col in df2:
        if col not in df1:
            df1[col] = 0

    for row in df2.itertuples():
        idx = row.Index
        vals = {}
        for k, v in row._asdict().items():
            if k == 'Index':
                continue
            if k[0] == '_':
                k = df2.columns[int(k[1:])-1]
            vals[k] = v
        df1.loc[idx] = vals


def validate_source(ctx, param, value):
    if value == 'all':
        return 'pypi', 'conda'
    else:
        return (value,)


@click.command()
@click.option(
    '-s',
    '--sources',
    type=click.Choice(['pypi', 'conda', 'all'], case_sensitive=False),
    default='all',
    callback=validate_source,
    help='Download statistics data from given source',
)
@click.option(
    '-n',
    '--last',
    type=click.IntRange(1, 12, clamp=True),
    default=3,
    help='Download data for the last n months',
)
@click.option(
    '-a',
    '--all',
    default=False,
    is_flag=True,
    help='Download all data, not just recent data',
)
def main(sources, last, all):
    repos = XdevRepos()

    for source in sources:
        packages = repos.packages(source=source)
        method = getattr(download_stats, f'get_{source}_stats')

        statsfile = 'data' / Path(f'{source}_stats.csv')
        if statsfile.exists():
            print(f'Reading {source} statistics file...')
            df = pd.read_csv(statsfile)
            df['month'] = pd.to_datetime(df.month).dt.to_period('M')
            df = df.set_index('month')
        else:
            print(f'Initializing {source} statistics...')
            df = pd.DataFrame()
            df.index = pd.period_range(
                start='2019-01',
                periods=0,
                freq='M',
                name='month',
            )

        if all:
            print(f'Downloading all {source} statistics...')
            df_ = method(packages=packages)
            update_dataframe(df, df_)

        else:
            print(f'Updating {source} statistics for last {last} months...')
            now = datetime.now()
            for i in range(last-1, -1, -1):
                dt = now - relativedelta(months=i)
                year, month = dt.year, dt.month

                print(f'  Updating month {year:04d}-{month:02d}')
                df_ = method(packages=packages, year=year, month=month)
                update_dataframe(df, df_)

        df.to_csv(statsfile)
        print('Done.')


if __name__ == '__main__':
    main()