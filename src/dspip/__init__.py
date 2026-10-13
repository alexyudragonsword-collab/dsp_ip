"""dspip: bit-true DSP IP library.

Every IP ships three things that must agree:

1. a Python fixed-point reference (the truth, pure integer arithmetic);
2. a SystemVerilog implementation;
3. a per-sample lockstep check (``tools/lockstep.py <ip>``) run in CI.

See ``AGENTS.md`` for the rules and ``ip/<name>/ip.yaml`` for each IP's contract.
"""

__version__ = "0.1.0"
