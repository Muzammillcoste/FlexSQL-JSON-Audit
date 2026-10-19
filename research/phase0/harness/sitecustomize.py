"""Auto-load the Phase 0 trace harness in every Python process that FlexSQL
spawns (main process, ProcessPoolExecutor workers), without editing upstream.

Active only when FLEXSQL_P0_TRACE is set. Patches lazily: the wrapper is applied
right after ``openai.resources.chat.completions.completions`` is first imported,
so processes that never import openai (interpreter/program subprocesses) pay
nothing.
"""
import os
import sys

if os.environ.get("FLEXSQL_P0_TRACE"):
    import importlib.abc
    import importlib.util

    _TARGET = "openai.resources.chat.completions.completions"

    class _P0Hook(importlib.abc.MetaPathFinder):
        def find_spec(self, name, path=None, target=None):
            if name != _TARGET:
                return None
            sys.meta_path.remove(self)
            spec = importlib.util.find_spec(name)
            if spec is None or spec.loader is None:
                return spec
            orig_exec = spec.loader.exec_module

            def exec_module(module):
                orig_exec(module)
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import p0_trace
                p0_trace.patch_class(module.Completions)

            spec.loader.exec_module = exec_module
            return spec

    sys.meta_path.insert(0, _P0Hook())
