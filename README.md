# SOLID 原則に基づく FastAPI バックエンド

FastAPI バックエンドアプリケーションです。GCP Cloud SQL との統合に対応し、Docker でコンテナ化されています。

## 🏗️ アーキテクチャ

このプロジェクトは Clean Architecture の原則に従い、関心の分離を明確にしています。

-   **API レイヤ**：FastAPI エンドポイントが HTTP リクエスト/レスポンスを処理
-   **サービスレイヤ**：ビジネスロジックやドメインルール
-   **リポジトリレイヤ**：データアクセスの抽象化
-   **モデルレイヤ**：データベースエンティティとスキーマ

## 🚀 主な特徴

-   ✅ **SOLID 原則**：単一責任、オープン/クローズ、リスコフ置換、インターフェース分離、依存性逆転
-   ✅ **FastAPI**：自動 API ドキュメント付きのモダンで高速な Web フレームワーク
-   ✅ **GCP Cloud SQL**：コネクションプーリング対応の PostgreSQL 統合
-   ✅ **JWT 認証**：安全なトークンベースの認証
-   ✅ **Docker 対応**：本番用マルチステージ Dockerfile
-   ✅ **DB マイグレーション**：Alembic によるスキーマ管理
-   ✅ **型安全性**：Pydantic による包括的な型ヒントとバリデーション
-   ✅ **エラーハンドリング**：ドメイン固有の例外と適切な HTTP レスポンス
-   ✅ **ヘルスチェック**：内蔵のヘルスチェックエンドポイント
-   ✅ **API ドキュメント**：自動生成 OpenAPI/Swagger

## 📋 前提条件

-   Python 3.11 以上
-   Docker & Docker Compose
-   PostgreSQL（または GCP Cloud SQL）
-   Google Cloud SDK（GCP デプロイ用）

## 🛠️ ローカル開発セットアップ

### 1. クローンとセットアップ

```bash
# リポジトリのクローン
git clone <repository-url>
cd backend

```

### 2. 環境設定

`.env.example`を参考に`.env`ファイルを作成してください：

```bash
# テンプレートをコピー
cp .env.example .env

# 設定を編集
vim .env
```

### 3. Docker で起動

```bash
# 全サービス起動
docker-compose up --build

# 特定サービスのみ起動 （今はつかはない）
docker-compose up fastapi postgres redis

# GCP Cloud SQL Proxy有効化で起動 （今はつかはない）
docker-compose --profile gcp up
```

> **⚠️ 注意**
>
> migration できていなくてエラーが出る際は以下のコマンドを実行してください：
>
> ```bash
> # DBマイグレーションの実行
> docker-compose exec fastapi alembic upgrade head
> ```

## オプションセットアップ

### 3. データベースセットアップ

#### オプション A：Docker でローカル PostgreSQL

```bash
# Docker ComposeでPostgreSQLを起動
docker-compose up postgres redis -d

# DBマイグレーションの実行
alembic upgrade head
```

#### オプション B：GCP Cloud SQL

```bash
# Cloud SQL Proxyをインストール
curl -o cloud_sql_proxy https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64
chmod +x cloud_sql_proxy

# Cloud SQL Proxyを起動
./cloud_sql_proxy -instances=PROJECT:REGION:INSTANCE=tcp:5432

# マイグレーションを実行
alembic upgrade head
```

API は以下で利用可能です：

-   **API**: [http://localhost:8000](http://localhost:8000)
-   **ドキュメント**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
-   **ヘルスチェック**: [http://localhost:8000/health](http://localhost:8000/health)

## 🐳 Docker デプロイ

### ローカル開発

```bash
# 全サービス起動
docker-compose up --build

# 特定サービスのみ起動 今つかはない)
docker-compose up fastapi postgres redis

# GCP Cloud SQL Proxy有効化で起動 (今つかはない)
docker-compose --profile gcp up
```

### 本番ビルド

```bash
# 本番用イメージビルド
docker build -t fastapi-backend .

# 本番用コンテナ実行
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://user:pass@host:5432/db \
  -e SECRET_KEY=your-secret-key \
  fastapi-backend
```

## 🗄️ データベースマイグレーション

```bash
# 新しいマイグレーションを作成
alembic revision --autogenerate -m "変更内容の説明"

# マイグレーションの適用
docker-compose exec fastapi alembic upgrade

# 前のマイグレーションにダウングレード
alembic downgrade -1

# マイグレーション履歴の確認
alembic history
```

## 🏛️ プロジェクト構成

```
backend/
├── app/
│   ├── api/                 # APIレイヤ
│   │   └── v1/
│   │       ├── endpoints/   # APIエンドポイント
│   │       └── api.py       # APIルーター
│   ├── core/               # コア機能
│   │   ├── config.py       # 設定
│   │   ├── database.py     # DBセットアップ
│   │   ├── dependencies.py # 依存性注入
│   │   ├── exceptions.py   # カスタム例外
│   │   └── security.py     # セキュリティユーティリティ
│   ├── models/             # DBモデル
│   ├── repositories/       # データアクセスレイヤ
│   ├── schemas/            # Pydanticスキーマ
│   ├── services/           # ビジネスロジック
│   ├── utils/              # ユーティリティ関数
│   └── main.py            # アプリケーションエントリーポイント
├── alembic/               # DBマイグレーション
├── scripts/               # DBスクリプト
├── tests/                 # テストファイル
├── Dockerfile            # Docker設定
├── docker-compose.yml    # Docker Compose設定
├── requirements.txt      # Python依存関係
└── alembic.ini          # Alembic設定
```

## 🧪 テスト

```bash
# テスト依存のインストール
pip install pytest pytest-asyncio httpx

# テストの実行
pytest

# カバレッジ付きで実行
pytest --cov=app --cov-report=html
```

## ☁️ GCP デプロイ

### 1. Cloud SQL セットアップ

```bash
# Cloud SQLインスタンス作成
gcloud sql instances create fastapi-db \
  --database-version=POSTGRES_14 \
  --tier=db-f1-micro \
  --region=us-central1

# データベース作成
gcloud sql databases create fastapi_db --instance=fastapi-db

# ユーザー作成
gcloud sql users create fastapi-user \
  --instance=fastapi-db \
  --password=secure-password
```

### 2. Cloud Run デプロイ

```bash
# コンテナイメージのビルドとプッシュ
docker build -t gcr.io/PROJECT_ID/fastapi-backend .
docker push gcr.io/PROJECT_ID/fastapi-backend

# Cloud Runにデプロイ
gcloud run deploy fastapi-backend \
  --image gcr.io/PROJECT_ID/fastapi-backend \
  --platform managed \
  --region us-central1 \
  --add-cloudsql-instances PROJECT_ID:REGION:INSTANCE_NAME \
  --set-env-vars DATABASE_URL="postgresql://user:pass@/dbname?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME"
```

## 📝 設定リファレンス

### 環境変数

| 変数名                      | 説明                               | デフォルト                            |
| --------------------------- | ---------------------------------- | ------------------------------------- |
| `PROJECT_NAME`              | アプリケーション名                 | FastAPI Backend with SOLID Principles |
| `ENVIRONMENT`               | 実行環境（development/production） | development                           |
| `SECRET_KEY`                | JWT シークレットキー               | 必須                                  |
| `DB_USER`                   | データベースユーザー名             | postgres                              |
| `DB_PASSWORD`               | データベースパスワード             | 必須                                  |
| `DB_NAME`                   | データベース名                     | fastapi_db                            |
| `CLOUD_SQL_CONNECTION_NAME` | GCP Cloud SQL 接続名               | GCP で必須                            |
| `GOOGLE_CLOUD_PROJECT`      | GCP プロジェクト ID                | GCP で必須                            |

## 🤝 コントリビューション

1. SOLID 原則を守ってください
2. すべての関数に型ヒントを追加してください
3. 充実した docstring を書いてください
4. 新機能にはテストを追加してください
5. ドキュメントも更新してください

## 📄 ライセンス

このプロジェクトは MIT ライセンスで提供されています。
