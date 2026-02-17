from pydantic import BaseModel, Field

class GitHubConfig(BaseModel):
    token: str = Field(..., description="Токен для доступа к API GitHub")
    owner: str = Field(..., description="Владелец репозитория, над которым будет осуществляться работы")
    repo: str = Field(..., description="Репозиторий, над которым будет осуществляться работы")