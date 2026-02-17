import requests
from http_toolkit.validator import validate, RetryCondition

API_URL = 'https://api.github.com'
GRAPHQL_URL = 'https://api.github.com/graphql'


class Base:
    """Основной класс для работы с API GitHub"""

    def __init__(self, token: str, owner: str, repo: str):
        """
        Инициализация класса

        :param token: Токен для работы с API GitHub.
        :param owner: Владелец репозитория, над которым будет осуществляться работы.
        :param repo: Репозиторий, над которым будет осуществляться работы.
        """
        self._headers = {
            'Authorization': f'bearer {token}',
            'Accept': 'application/vnd.github+json'
        }
        self.owner = owner
        self.repo = repo

        self.projects = Project(token, owner, repo)
        self.issues = Issue(token, owner, repo)


class Project:
    """Класс для работы с проектами API GitHub"""

    def __init__(self, token: str, owner: str, repo: str):
        """
        Инициализация класса

        :param token: Токен для работы с API GitHub.
        :param owner: Владелец репозитория, над которым будет осуществляться работы.
        :param repo: Репозиторий, над которым будет осуществляться работы.
        """
        self._headers = {
            'Authorization': f'bearer {token}',
            'Accept': 'application/vnd.github+json'
        }
        self.owner = owner
        self.repo = repo

    @validate(retry=RetryCondition(statuses=[500+i for i in range(100)], delay_sec=1, max_count=2))
    def get_list(self) -> requests.Response:
        """Возвращает список проектов"""
        query = """
                query($login: String!) {
                  user(login: $login) {
                    projectsV2(first: 50) {
                      nodes {
                        id
                        title
                      }
                    }
                  }
                }
                """
        variables = {"login": self.owner}
        return requests.post(
            url=GRAPHQL_URL,
            headers=self._headers,
            json={"query": query, "variables": variables},
            timeout=20,
        )

    @validate(retry=RetryCondition(statuses=[500+i for i in range(100)], delay_sec=1, max_count=2))
    def add_issue(self, project_id: str, issue_id: str) -> requests.Response:
        """
        Добавляет issue в проект

        :param project_id: ID проекта
        :param issue_id: ID issue
        """

        mutation_add = """
                mutation($projectId: ID!, $contentId: ID!) {
                  addProjectV2ItemById(input: {
                    projectId: $projectId,
                    contentId: $contentId
                  }) {
                    item {
                      id
                    }
                  }
                }
                """
        variables_add = {
            "projectId": project_id,
            "contentId": issue_id,
        }
        return requests.post(
            url=GRAPHQL_URL,
            headers=self._headers,
            json={"query": mutation_add, "variables": variables_add},
            timeout=20,
        )

    @validate(retry=RetryCondition(statuses=[500+i for i in range(100)], delay_sec=1, max_count=2))
    def get_fields(self, project_id: str) -> requests.Response:
        """
        Возвращает все поля проекта GitHub Projects v2

        :param project_id: ID проекта
        """
        query = """
        query ($projectId: ID!) {
          node(id: $projectId) {
            ... on ProjectV2 {
              fields(first: 50) {
                nodes {

                  # ВСЕ поля имеют это
                  ... on ProjectV2Field {
                    id
                    name
                    dataType
                  }

                  # Только Single Select (Status, Priority и т.п.)
                  ... on ProjectV2SingleSelectField {
                    id
                    name
                    options {
                      id
                      name
                    }
                  }

                  # Только Iteration
                  ... on ProjectV2IterationField {
                    configuration {
                      iterations {
                        id
                        title
                      }
                    }
                  }

                }
              }
            }
          }
        }
        """

        return requests.post(
            url=GRAPHQL_URL,
            headers=self._headers,
            json={
                "query": query,
                "variables": {"projectId": project_id},
            },
            timeout=20,
        )

class Issue:
    """Класс для работы с задачами API GitHub"""

    def __init__(self, token: str, owner: str, repo: str):
        """
        Инициализация класса

        :param token: Токен для работы с API GitHub.
        :param owner: Владелец репозитория, над которым будет осуществляться работы.
        :param repo: Репозиторий, над которым будет осуществляться работы.
        """
        self._headers = {
            'Authorization': f'bearer {token}',
            'Accept': 'application/vnd.github+json'
        }
        self.owner = owner
        self.repo = repo

    @validate(retry=RetryCondition(statuses=[500+i for i in range(100)], delay_sec=1, max_count=2))
    def create(self, title: str, body: str | None = None, assignee_login: list[str] = None,
               label_name: list[str] = None) -> requests.Response:
        """
        Создаёт issue в GitHub.

        :param title: Заголовок issue
        :param body: Описание issue
        :param assignee_login: GitHub логины для назначения
        :param label_name: Список меток

        :return: URL созданного issue
        """
        return requests.post(
            url=f'{API_URL}/repos/{self.owner}/{self.repo}/issues',
            headers=self._headers,
            json={
                "title": title,
                "body": body,
                "assignees": assignee_login,
                "labels": label_name
            },
            timeout=20,
        )

    @validate(retry=RetryCondition(statuses=[500+i for i in range(100)], delay_sec=1, max_count=2))
    def change_status(self, project_id: str, issue_id: str, field_id: str, status_id: str) -> requests.Response:
        """
        Устанавливает статус issue
        :param project_id: ID проекта
        :param issue_id: ID issue
        :param field_id: ID поля
        :param status_id: ID статуса
        """
        mutation_status = """
                    mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
                      updateProjectV2ItemFieldValue(
                        input: {
                          projectId: $projectId,
                          itemId: $itemId,
                          fieldId: $fieldId,
                          value: {
                            singleSelectOptionId: $optionId
                          }
                        }
                      ) {
                        projectV2Item {
                          id
                        }
                      }
                    }
                    """
        variables_status = {
            "projectId": project_id,
            "itemId": issue_id,
            "fieldId": field_id,
            "optionId": status_id,
        }
        return requests.post(
            url=GRAPHQL_URL,
            headers=self._headers,
            json={"query": mutation_status, "variables": variables_status},
            timeout=20,
        )
