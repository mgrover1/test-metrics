from pathlib import Path
import yaml

ROOT_DIR = Path(__file__).parent.parent.parent.absolute()


class TargetRepos:

    def __init__(self) -> None:
        self._filename = Path(ROOT_DIR / 'data' / Path(__file__).name).with_suffix('.yml')
        self._repos = {}
        self._read()

    def _parse_github_string(self, gh_string: str) -> None:
        try:
            gh_org, gh_repo = gh_string.split('/', 1)
        except ValueError:
            gh_org = None
            gh_repo = None
        return gh_org, gh_repo

    def _read(self) -> None:
        with open(self._filename) as yml:
            _repos = yaml.safe_load(yml)

        for repo in _repos:
            gh_org = None
            gh_repo = None
            if isinstance(_repos[repo], str):
                gh_org, gh_repo = self._parse_github_string(_repos[repo])
                pypi_pkg = gh_repo
                conda_pkg = gh_repo
            elif isinstance(_repos[repo], dict):
                if 'github' in _repos[repo]:
                    gh = _repos[repo]['github']
                    if isinstance(gh, str):
                        gh_org, gh_repo = self._parse_github_string(gh)
                    elif isinstance(gh, dict):
                        gh_org = gh.get('org', None)
                        gh_repo = gh.get('repo', None)
                pypi_pkg = _repos[repo]['pypi'] if 'pypi' in _repos[repo] else gh_repo
                conda_pkg = _repos[repo]['conda'] if 'conda' in _repos[repo] else gh_repo

            self._repos[repo] = dict(org=gh_org, repo=gh_repo, pypi=pypi_pkg, conda=conda_pkg)

    def packages(self, source='pypi'):
        packages = []
        for repo in self._repos:
            if source in self._repos[repo] and self._repos[repo][source]:
                packages.append(self._repos[repo][source])
        return packages

    def __len__(self):
        return len(self._repos)

    def keys(self):
        return self._repos.keys()

    def values(self):
        return self._repos.values()

    def items(self):
        return self._repos.items()

    def __getitem__(self, key):
        return self._repos[key]