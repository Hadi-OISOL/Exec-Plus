"""Use case: Runs control-plane schema migrations.

What it does: Reads environment configuration and supports online/offline Alembic execution.
"""

from alembic import context
from sqlalchemy import create_engine

from execplus.config import Settings
from execplus.infrastructure.persistence.schema import metadata

if context.is_offline_mode():
    context.configure(url=Settings().database_url, target_metadata=metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
elif context.config.attributes.get("connection") is not None:
    context.configure(connection=context.config.attributes["connection"], target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(Settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
