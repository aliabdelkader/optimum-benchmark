import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from omegaconf import OmegaConf

from ...env_utils import is_rocm_system
from ...import_utils import torch_version
from ..config import BackendConfig
from ..peft_utils import PEFT_CONFIGS, PEFT_TASKS_TYPES

OmegaConf.register_new_resolver("device_count", lambda: len(os.environ.get("CUDA_VISIBLE_DEVICES", "").split(",")))
OmegaConf.register_new_resolver("is_inference", lambda benchmark_name: benchmark_name == "inference")
OmegaConf.register_new_resolver("pytorch_version", torch_version)

DEVICE_MAPS = ["auto", "sequential"]
AMP_DTYPES = ["bfloat16", "float16"]
TORCH_DTYPES = ["bfloat16", "float16", "float32", "auto"]

QUANTIZATION_CONFIGS = {
    "gptq": {"dataset": ["lorem ipsum dolor sit amet consectetur"]},
    "bnb": {"llm_int8_threshold": 0.0},
    "awq": {},
}
COMPILE_CONFIG = {
    "fullgraph": False,
    "dynamic": False,
    "backend": "inductor",
    "mode": None,
    "options": None,
    "disable": False,
}


@dataclass
class PyTorchConfig(BackendConfig):
    name: str = "pytorch"
    version: str = "${pytorch_version:}"
    _target_: str = "optimum_benchmark.backends.pytorch.backend.PyTorchBackend"

    # load options
    no_weights: bool = False
    device_map: Optional[str] = None
    torch_dtype: Optional[str] = None

    # inference options
    eval_mode: bool = "${is_inference:${benchmark.name}}"
    disable_grad: bool = "${is_inference:${benchmark.name}}"

    # automatic mixed precision options
    amp_autocast: bool = False
    amp_dtype: Optional[str] = None

    # compilation options
    torch_compile: bool = False
    torch_compile_config: Dict[str, Any] = field(default_factory=dict)

    # optimization options
    to_bettertransformer: bool = False
    use_flash_attention_2: bool = False

    # quantization options
    quantization_scheme: Optional[str] = None
    quantization_config: Dict[str, Any] = field(default_factory=dict)

    # distributed inference options
    data_parallel: bool = False
    deepspeed_inference: bool = False
    deepspeed_inference_config: Dict[str, Any] = field(default_factory=dict)

    # peft options
    peft_strategy: Optional[str] = None
    peft_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()

        if self.torch_compile:
            self.torch_compile_config = OmegaConf.to_object(OmegaConf.merge(COMPILE_CONFIG, self.torch_compile_config))

        if self.device_map is not None and self.device_map not in DEVICE_MAPS:
            raise ValueError(f"`device_map` must be one of {DEVICE_MAPS}. Got {self.device_map} instead.")

        if self.torch_dtype is not None and self.torch_dtype not in TORCH_DTYPES:
            raise ValueError(f"`torch_dtype` must be one of {TORCH_DTYPES}. Got {self.torch_dtype} instead.")

        if self.amp_dtype is not None and self.amp_dtype not in AMP_DTYPES:
            raise ValueError(f"`amp_dtype` must be one of {AMP_DTYPES}. Got {self.amp_dtype} instead.")

        if self.quantization_scheme is not None:
            if self.quantization_scheme not in QUANTIZATION_CONFIGS:
                raise ValueError(
                    f"`quantization_scheme` must be one of {list(QUANTIZATION_CONFIGS.keys())}. Got {self.quantization_scheme} instead."
                )
            if self.quantization_config:
                QUANTIZATION_CONFIG = QUANTIZATION_CONFIGS[self.quantization_scheme]
                self.quantization_config = OmegaConf.to_object(
                    OmegaConf.merge(QUANTIZATION_CONFIG, self.quantization_config)
                )

        if self.peft_strategy is not None:
            if self.peft_strategy not in PEFT_CONFIGS:
                raise ValueError(
                    f"`peft_strategy` must be one of {list(PEFT_CONFIGS.keys())}. Got {self.peft_strategy} instead."
                )
            PEFT_CONFIG = PEFT_CONFIGS[self.peft_strategy]
            self.peft_config = OmegaConf.to_object(OmegaConf.merge(PEFT_CONFIG, self.peft_config))

            if self.peft_config["task_type"] is None:
                raise ValueError(f"`peft_config.task_type` must be set to one of the following {PEFT_TASKS_TYPES}")

        if self.quantization_scheme == "bnb" and is_rocm_system():
            raise ValueError(
                "bitsandbytes is not supported on RoCm GPUs. Please disable it in the yaml configuration used."
            )
