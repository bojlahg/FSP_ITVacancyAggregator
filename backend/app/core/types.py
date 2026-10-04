from enum import StrEnum

from sqlalchemy import CheckConstraint, MetaData
from sqlalchemy import Enum as SAEnum


def enum_type(enum_cls: type[StrEnum]) -> SAEnum:
    """VARCHAR вместо нативного PG enum: новые значения без ALTER TYPE. CHECK — в add_enum_checks."""
    return SAEnum(
        enum_cls,
        name=enum_cls.__name__.lower(),
        native_enum=False,
        create_constraint=False,
        length=32,
        values_callable=lambda members: [member.value for member in members],
    )


def add_enum_checks(metadata: MetaData) -> None:
    """Ровно один CHECK на enum-колонку: встроенный CHECK sa.Enum autogenerate Alembic дублирует."""
    for table in metadata.tables.values():
        existing = {constraint.name for constraint in table.constraints}
        for column in table.columns:
            if not isinstance(column.type, SAEnum) or column.type.native_enum:
                continue
            name = f"{column.name}_enum"
            if name in existing:
                continue
            values = ", ".join(f"'{value}'" for value in column.type.enums)
            table.append_constraint(CheckConstraint(f"{column.name} IN ({values})", name=name))
