"""Layer 2: local, self-trained neural brain. No pretrained/external decision models."""
from .network import MultiTimeframeBrain, set_deterministic
from .inference import infer
from .brainflow import calculate_brainflow
from .decision import decide
