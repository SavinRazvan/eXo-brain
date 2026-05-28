"""
File: __init__.py
Path: packages/exo-adapter-echo/src/exo_adapter_echo/__init__.py
Role: Public exports for the portable echo adapter package.
Used By:
 - adapter factory and external install smoke
Depends On:
 - exo_adapter_echo.runtime
Notes:
 - No provider SDK dependencies; safe second package for portability proofs.
"""

from exo_adapter_echo.runtime import EchoRuntimeAdapter, load_adapter

__all__ = ["EchoRuntimeAdapter", "load_adapter"]
