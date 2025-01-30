from typing import Any, Callable, Dict, Literal
import hashlib
import json


def generate_lock_name(
    func: Callable | None,
    lock_scope: Literal["module", "method", "parameters"],
    params: Dict[str, Any],
) -> str:
    if lock_scope == "module" and func is not None:
        hash_input = f"{func.__module__}"
    elif lock_scope == "method" and func is not None:
        hash_input = f"{func.__module__}.{func.__name__}"
    elif lock_scope == "parameters":
        hash_input = json.dumps(params, sort_keys=True, default=str)
    else:
        raise ValueError(f"Invalid lock scope: {lock_scope}")
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
