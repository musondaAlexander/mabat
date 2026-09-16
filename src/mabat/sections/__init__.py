"""One sub-package per observed domain: cpu, memory, system, storage, gpu, sensors, network.

Each owns its models, collector and providers, imports only ``mabat._shared``, and never
another section. Public entry points (``mabat.cpu()`` ...) are re-exported from ``mabat``.
"""
