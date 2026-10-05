from typing import Optional

import requests

API_URL = 'https://api.github.com'


class GitHub:
    def __init__(self, token: Optional[str]):
        self.token = token
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/vnd.github+json'
        self.session.headers['X-GitHub-Api-Version'] = '2022-11-28'
        if token:
            self.session.headers['Authorization'] = f'Bearer {token}'

    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        response = self.session.request(method, f'{API_URL}{path}', timeout=30, **kwargs)
        if not response.ok and response.status_code != 404:
            raise RuntimeError(f'{method} {path} failed: {response.status_code} {response.text}')
        return response

    def clone_url(self, repo: str) -> str:
        if self.token:
            return f'https://x-access-token:{self.token}@github.com/{repo}.git'
        return f'https://github.com/{repo}.git'

    def default_branch(self, repo: str) -> str:
        response = self._request('GET', f'/repos/{repo}')
        if response.status_code == 404:
            raise RuntimeError(f'Repository {repo} not found or not accessible')
        return response.json()['default_branch']

    def branch_exists(self, repo: str, branch: str) -> bool:
        return self._request('GET', f'/repos/{repo}/branches/{branch}').status_code != 404

    def create_pull_request(self, repo: str, head: str, base: str, title: str, body: str) -> dict:
        response = self._request('POST', f'/repos/{repo}/pulls',
                                 json={'title': title, 'head': head, 'base': base, 'body': body})
        if response.status_code == 404:
            raise RuntimeError(f'Failed to create pull request in {repo}, does the token have access?')
        return response.json()

    def add_assignees(self, repo: str, number: int, assignees: list[str]):
        if assignees:
            self._request('POST', f'/repos/{repo}/issues/{number}/assignees', json={'assignees': assignees})
