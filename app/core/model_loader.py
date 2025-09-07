"""
グローバルなSentence Transformerモデルのロードとキャッシュ管理
アプリケーション起動時に一度だけモデルをロードし、全リクエストで共有
"""
from typing import Optional
import time
from sentence_transformers import SentenceTransformer


# グローバル変数でモデルを保持
_model: Optional[SentenceTransformer] = None
_model_load_time: Optional[float] = None


def get_model() -> Optional[SentenceTransformer]:
    """
    Sentence Transformerモデルを取得
    初回呼び出し時にモデルをロードし、以降はキャッシュされたモデルを返す
    """
    global _model
    if _model is None:
        load_model()
    return _model


def load_model() -> None:
    """
    モデルを明示的にロード
    アプリケーション起動時に呼び出される
    """
    global _model, _model_load_time
    
    if _model is not None:
        print("✅ モデルは既にロード済みです")
        return
    
    try:
        start_time = time.time()
        model_name = "paraphrase-multilingual-MiniLM-L12-v2"
        
        print(f"🚀 Sentence Transformerモデルロード開始: {model_name}")
        
        # モデルをロード（CPUまたはCUDAを自動選択）
        _model = SentenceTransformer(
            model_name,
            device="cpu"  # GPUがある場合は "cuda" に変更可能
        )
        
        load_time = time.time() - start_time
        _model_load_time = load_time
        
        print(f"✅ モデルロード完了: {load_time:.2f}秒")
        
    except Exception as e:
        print(f"❌ モデルロード失敗: {str(e)}")
        _model = None
        raise


def warmup() -> None:
    """
    モデルのウォームアップ
    初回推論の遅延を避けるため、ダミーテキストで事前実行
    """
    if _model is None:
        load_model()
    
    if _model is not None:
        try:
            print("🔥 モデルウォームアップ開始...")
            start_time = time.time()
            
            # 複数言語でウォームアップ（日本語、韓国語、英語）
            warmup_texts = [
                "東京の静かな公園を探しています",
                "서울의 조용한 공원을 찾고 있습니다",
                "Looking for quiet parks in Barcelona"
            ]
            
            # エンコード実行（キャッシュも温める）
            _ = _model.encode(warmup_texts)
            
            warmup_time = time.time() - start_time
            print(f"✅ ウォームアップ完了: {warmup_time:.2f}秒")
            
        except Exception as e:
            print(f"⚠️ ウォームアップ失敗（続行可能）: {str(e)}")


def get_model_info() -> dict:
    """
    ロードされたモデルの情報を取得
    """
    if _model is None:
        return {
            "loaded": False,
            "model_name": None,
            "load_time": None
        }
    
    return {
        "loaded": True,
        "model_name": "paraphrase-multilingual-MiniLM-L12-v2",
        "load_time": _model_load_time,
        "embedding_dimension": 384
    }


def clear_model() -> None:
    """
    モデルをメモリから解放（テスト用）
    """
    global _model, _model_load_time
    _model = None
    _model_load_time = None
    print("🗑️ モデルをメモリから解放しました")