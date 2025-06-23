import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

# アプリをインポートできるように親ディレクトリをパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from app.core.config import settings
from app.models.base import Base

# これはAlembic Configオブジェクトで、.iniファイル内の値へのアクセスを提供します
config = context.config

# sqlalchemy.urlを私たちの設定で上書き
config.set_main_option("sqlalchemy.url", settings.database_url)

# Pythonログ用の設定ファイルを解釈
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 自動生成サポート用のターゲットメタデータ
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    'オフライン'モードでマイグレーションを実行。

    これはEngineではなくURLだけでコンテキストを設定しますが、
    ここではEngineも受け入れ可能です。Engineの作成をスキップすることで、
    DBAPIさえ利用可能である必要がありません。

    ここでのcontext.execute()の呼び出しは、指定された文字列を
    スクリプト出力に出力します。
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    'オンライン'モードでマイグレーションを実行。

    このシナリオでは、Engineを作成し、
    コンテキストに接続を関連付ける必要があります。
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
