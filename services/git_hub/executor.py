from .client import Base as Client
from .types import GitHubConfig


class Base:
    """Основной класс для работы с API GitHub"""

    def __init__(self, config: GitHubConfig):
        """
        Инициализация класса

        :param config: Конфигурация для работы с API GitHub.
        """
        self._config = config
        self.api = Client(config.token, config.owner, config.repo)

        self.project = Project(config)
        self.issues = Issue(config)


class Project:
    """Класс для работы с проектами API GitHub"""

    def __init__(self, config: GitHubConfig):
        """
        Инициализация класса

        :param config: Конфигурация для работы с API GitHub.
        """
        self._config = config
        self.api = Client(config.token, config.owner, config.repo)

    def get_list(self) -> dict[str, str]:
        """Возвращает список проектов"""
        projects_response = self.api.projects.get_list()
        projects_answer = projects_response.json()
        projects = projects_answer.get("data", {}).get("user", {}).get("projectsV2", {}).get("nodes", None)
        if projects:
            return {p['title']: p['id'] for p in projects}
        return {}

    def add_issue(self, project_name: str, issue_id: str) -> str | None:
        """
        Добавляет issue в проект

        :param project_name: Название проекта
        :param issue_id: ID issue
        :return: True если добавлено, иначе False
        """
        available_projects = self.get_list()
        if project_name in available_projects:
            self.api.projects.add_issue(
                project_id=available_projects[project_name],
                issue_id=issue_id
            )
            return available_projects[project_name]
        return None

    def get_fields(self, project_id: str) -> dict:
        """
        Возвращает поля проекта

        :param project_id: ID проекта
        """
        fields_response = self.api.projects.get_fields(project_id)
        if fields_response.status_code > 300:
            raise Exception(f"Не удалось получить поля проекта. Ошибка: {fields_response.text}")

        nodes = (
            fields_response.json()
            .get("data", {})
            .get("node", {})
            .get("fields", {})
            .get("nodes", [])
        )

        return {
            n['name']: {
                'id': n['id'],
                'options': {
                    o['name']: o['id']
                    for o in n.get('options', {})
                }
            } for n in nodes}


class Issue:
    """Класс для работы с задачами API GitHub"""

    def __init__(self, config: GitHubConfig):
        """
        Инициализация класса

        :param config: Конфигурация для работы с API GitHub.
        """
        self._config = config
        self.api = Client(config.token, config.owner, config.repo)

    def create(self, title: str, body: str | None = None, status: str = None, assignee_login: list[str] = None,
               label_name: list[str] = None, project: str = None) -> str:
        """
        Создаёт issue в GitHub.

        :param title: Заголовок issue
        :param body: Описание issue
        :param status: Статус issue
        :param assignee_login: GitHub логины для назначения
        :param label_name: Список меток
        :param project: Проект в который необходимо добавить issue

        :return: URL созданного issue
        """
        create_issue_response = self.api.issues.create(
            title=title,
            body=body,
            assignee_login=assignee_login,
            label_name=label_name
        )
        if create_issue_response.status_code > 300:
            raise Exception(f"Не удалось создать issue. Ошибка: {create_issue_response.text}")

        create_issue_answer = create_issue_response.json()
        issue_id = create_issue_answer['node_id']
        issue_url = create_issue_answer['html_url']

        if project:
            projects_executor = Project(self._config)
            project_id = projects_executor.add_issue(project, issue_id)
            if not project_id:
                raise Exception(f"Не удалось добавить issue в проект {project}")
        if status:
            if not self.change_status(project, issue_id, status):
                raise Exception(f"Не удалось изменить статус issue на {status}")

        return issue_url


    def change_status(self, project_name: str, issue_id: str, status: str) -> bool:
        """
        Изменяет статус issue в проекте

        :param project_name: Название проекта
        :param issue_id: ID issue
        :param status: Название статуса

        :return: True если изменено, иначе False
        """
        projects_executor = Project(self._config)

        project_id = projects_executor.get_list()[project_name]

        fields = projects_executor.get_fields(project_id)
        filed_id = fields['Status']['id']
        status_id = fields['Status']['options'][status]

        status_response = self.api.issues.change_status(project_id, issue_id, filed_id, status_id)
        if status_response.status_code > 300:
            return False
        return True
