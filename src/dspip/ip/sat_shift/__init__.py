"""sat_shift: rounding arithmetic right shift + saturation — the smallest real IP.

It is the primitive every other IP's output stage uses (``dpd_poly`` instantiates it), and
the IP the lockstep scaffold is proven on before anything bigger is built.
"""
