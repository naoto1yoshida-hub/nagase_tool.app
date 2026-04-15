"""
FAISSベクトル検索モジュール
CLIPベクトルを使用した高速類似検索
"""
import os
import numpy as np

from modules.config import Config
from modules.logger import get_logger

logger = get_logger('vector_index')

INDEX_PATH = os.path.join(Config.CACHE_DIR, "faiss_index.bin")
ID_MAP_PATH = os.path.join(Config.CACHE_DIR, "faiss_id_map.npy")

# FAISSの遅延インポート
_faiss = None


def _get_faiss():
    """FAISSを遅延ロードする"""
    global _faiss
    if _faiss is None:
        import faiss
        _faiss = faiss
    return _faiss


class VectorIndex:
    """CLIPベクトルのFAISSインデックス管理"""

    def __init__(self, dimension=512):
        self.dimension = dimension
        self.index = None
        self.id_map = []

    def build_index(self, vectors, drawing_paths):
        """ベクトル配列からインデックスを構築する"""
        faiss = _get_faiss()
        if len(vectors) == 0:
            self.index = faiss.IndexFlatIP(self.dimension)
            self.id_map = []
            return

        vectors = np.array(vectors, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        vectors = vectors / norms

        self.index = faiss.IndexFlatIP(self.dimension)
        self.index.add(vectors)
        self.id_map = list(drawing_paths)
        logger.info(f"FAISSインデックス構築完了: {len(drawing_paths)}件")

    def search_similar(self, query_vector, top_k=None):
        """類似ベクトルを検索する"""
        if top_k is None:
            top_k = Config.FAISS_TOP_K

        if self.index is None or self.index.ntotal == 0:
            return []

        query = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(query)
        if norm > 0:
            query = query / norm

        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if 0 <= idx < len(self.id_map):
                results.append((self.id_map[idx], float(score)))
        return results

    def add_vector(self, vector, drawing_path):
        """1件のベクトルをインデックスに追加する"""
        faiss = _get_faiss()
        if self.index is None:
            self.index = faiss.IndexFlatIP(self.dimension)

        v = np.array(vector, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(v)
        if norm > 0:
            v = v / norm
        self.index.add(v)
        self.id_map.append(drawing_path)

    def save(self):
        """インデックスをディスクに保存する"""
        faiss = _get_faiss()
        os.makedirs(Config.CACHE_DIR, exist_ok=True)
        if self.index is not None:
            faiss.write_index(self.index, INDEX_PATH)
        np.save(ID_MAP_PATH, np.array(self.id_map, dtype=object))
        logger.info(f"FAISSインデックス保存完了: {self.count}件")

    def load(self):
        """ディスクからインデックスを読み込む"""
        faiss = _get_faiss()
        if os.path.exists(INDEX_PATH) and os.path.exists(ID_MAP_PATH):
            self.index = faiss.read_index(INDEX_PATH)
            self.id_map = list(np.load(ID_MAP_PATH, allow_pickle=True))
            logger.info(f"FAISSインデックス読み込み完了: {self.count}件")
            return True
        return False

    @property
    def count(self):
        """インデックス内のベクトル数"""
        return self.index.ntotal if self.index else 0
