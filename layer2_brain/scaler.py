from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np

@dataclass(frozen=True)
class StandardScalerArtifact:
    feature_names: tuple[str, ...]
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    version: str = "scaler-v1"

    @classmethod
    def fit(cls, x: np.ndarray, feature_names: tuple[str, ...], version: str="scaler-v1"):
        if x.ndim != 2 or x.shape[1] != len(feature_names): raise ValueError("training matrix/schema mismatch")
        mean=x.mean(axis=0); scale=x.std(axis=0); scale=np.where(scale < 1e-12, 1.0, scale)
        return cls(feature_names, tuple(map(float,mean)), tuple(map(float,scale)), version)
    def transform(self, x: np.ndarray, feature_names: tuple[str,...]) -> np.ndarray:
        if tuple(feature_names)!=self.feature_names: raise ValueError("feature schema does not match fitted scaler")
        return (np.asarray(x,dtype=np.float32)-np.asarray(self.mean,dtype=np.float32))/np.asarray(self.scale,dtype=np.float32)
    def save(self,path:str|Path):
        path=Path(path)
        try:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(self.__dict__,indent=2),encoding='utf-8')
        except (OSError,TypeError,ValueError) as exc:
            raise RuntimeError(f"failed to save scaler artifact {path}: {exc}") from exc
    @classmethod
    def load(cls,path:str|Path):
        path=Path(path)
        try:
            d=json.loads(path.read_text(encoding='utf-8'))
            return cls(tuple(d['feature_names']),tuple(d['mean']),tuple(d['scale']),d['version'])
        except FileNotFoundError:
            raise
        except (OSError,json.JSONDecodeError,KeyError,TypeError,ValueError) as exc:
            raise RuntimeError(f"failed to load scaler artifact {path}: {exc}") from exc
