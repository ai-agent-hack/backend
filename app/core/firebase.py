import os
import json
import firebase_admin
from firebase_admin import credentials, auth
from typing import Optional
from app.core.config import settings


class FirebaseService:
    """Firebase Admin SDK service for authentication."""

    def __init__(self):
        if not firebase_admin._apps:
            try:
                # 方法1: JSON全体を環境変数から読み込み
                firebase_service_account_json = os.getenv(
                    "FIREBASE_SERVICE_ACCOUNT_JSON"
                ) or os.getenv("FIREBASE_SERVICE_ACCOUNT_KEY")
                if firebase_service_account_json:
                    try:
                        service_account_info = json.loads(firebase_service_account_json)
                        cred = credentials.Certificate(service_account_info)
                        firebase_admin.initialize_app(cred)
                        self._initialized = True
                        print(
                            "Firebase initialized from FIREBASE_SERVICE_ACCOUNT_JSON/KEY environment variable"
                        )
                        return
                    except json.JSONDecodeError as e:
                        print(f"Error parsing Firebase service account JSON: {e}")

                # すべての方法が失敗
                print(
                    "Warning: Firebase service account key not found in any location:"
                )
                print("- FIREBASE_SERVICE_ACCOUNT_JSON environment variable")
                print("- FIREBASE_SERVICE_ACCOUNT_KEY environment variable")
                print("- GOOGLE_APPLICATION_CREDENTIALS environment variable")
                print(
                    "- Individual environment variables (FIREBASE_PROJECT_ID, FIREBASE_PRIVATE_KEY, FIREBASE_CLIENT_EMAIL)"
                )
                print("- Service account key files")
                print("Firebase authentication will not work properly")
                self._initialized = False

            except Exception as e:
                print(f"Error initializing Firebase: {e}")
                self._initialized = False
        else:
            self._initialized = True

    async def verify_id_token(self, id_token: str) -> Optional[dict]:
        """
        Firebase IDトークンを検証してユーザー情報を返します。

        Args:
            id_token: Firebase ID token

        Returns:
            Decoded token data or None if invalid
        """
        if not hasattr(self, "_initialized") or not self._initialized:
            print("Firebase service not initialized")
            return None

        try:
            decoded_token = auth.verify_id_token(id_token)
            return decoded_token
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None

    async def get_user_by_uid(self, uid: str) -> Optional[dict]:
        """
        UIDでFirebaseユーザー情報を取得します。

        Args:
            uid: Firebase user UID

        Returns:
            User data or None if not found
        """
        if not hasattr(self, "_initialized") or not self._initialized:
            print("Firebase service not initialized")
            return None

        try:
            user_record = auth.get_user(uid)
            return {
                "uid": user_record.uid,
                "email": user_record.email,
                "display_name": user_record.display_name,
                "email_verified": user_record.email_verified,
                "disabled": user_record.disabled,
            }
        except Exception as e:
            print(f"Failed to get user by UID: {e}")
            return None


# Singleton instance
firebase_service = FirebaseService()


def get_firebase_service() -> FirebaseService:
    """Firebaseサービスインスタンスを返します。"""
    return firebase_service
