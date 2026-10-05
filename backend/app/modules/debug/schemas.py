from pydantic import Field

from app.core.schemas import ApiModel


class DebugStatus(ApiModel):
    enabled: bool = Field(description="Отладочный раздел включён (DEBUG_TOOLS=true)")
    actions: list[str] = Field(description="Действия, доступные текущей роли")
