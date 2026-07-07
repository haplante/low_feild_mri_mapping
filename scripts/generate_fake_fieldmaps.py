"""
Generate synthetic low-field MRI field-mapping Excel files.

Output format mimics the real robot-mapper exports:
  columns: "time stamp", x, y, z (mm), Bx (T), B (T)
  followed by a small summary footer (maximum / minimum / average / ppm rows).

File naming convention (parsed by the dashboard):
  <SCANNER>_DSV<diameter mm>_RES<step mm>_S<scan number>.xlsx

The underlying field of a given scanner is deterministic (seeded by the
scanner name), so S01/S02 are true scan-rescans of the same magnet (same
inhomogeneity pattern + small B0 drift + measurement noise), and a higher
resolution map of the same scanner samples the same field more densely.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data"
GAMMA = 42.577478518  # MHz/T proton gyromagnetic ratio


def scanner_field(name, B0):
    """Return a deterministic field function B(x,y,z) for a scanner.

    Built from low-order solid harmonics with amplitudes that give a few
    thousand ppm peak-to-peak over the DSV, similar to small Halbach magnets.
    """
    rng = np.random.default_rng(abs(hash(name)) % (2**32))
    # relative amplitudes (per mm, per mm^2) of the harmonic terms
    g = rng.uniform(-40e-6, 40e-6, 3)          # linear gradients /mm
    s = rng.uniform(-2.5e-6, 2.5e-6, 5)        # 2nd order /mm^2
    t = rng.uniform(-0.03e-6, 0.03e-6, 2)      # 3rd order /mm^3

    def field(x, y, z):
        rel = (
            g[0] * x + g[1] * y + g[2] * z
            + s[0] * (2 * z**2 - x**2 - y**2) / 2
            + s[1] * x * z + s[2] * y * z
            + s[3] * (x**2 - y**2) + s[4] * x * y
            + t[0] * z**3 + t[1] * z * (x**2 + y**2)
        )
        return B0 * (1.0 + rel)

    return field


def sphere_grid(dsv, res):
    """Cubic grid of pitch `res` mm clipped to a sphere of diameter `dsv` mm."""
    r = dsv / 2.0
    n = int(np.floor(r / res))
    ax = np.arange(-n, n + 1) * res
    X, Y, Z = np.meshgrid(ax, ax, ax, indexing="ij")
    m = X**2 + Y**2 + Z**2 <= r**2 + 1e-9
    pts = np.column_stack([X[m], Y[m], Z[m]])
    # robot visits slice by slice (z), then y, then x — like the real logs
    order = np.lexsort((pts[:, 0], pts[:, 1], pts[:, 2]))
    return pts[order]


def make_file(scanner, dsv, res, scan, B0, drift_ppm, noise_uT, t0, seed):
    field = scanner_field(scanner, B0)
    pts = sphere_grid(dsv, res)
    rng = np.random.default_rng(seed)

    B = field(pts[:, 0], pts[:, 1], pts[:, 2])
    B = B * (1.0 + drift_ppm * 1e-6)                  # rescan B0 drift
    B = B + rng.normal(0.0, noise_uT * 1e-6, len(B))  # probe noise (T)

    # Bx: main component is along -x in the robot frame, slightly smaller |.|
    eps = 6e-4 + 2e-4 * rng.standard_normal(len(B)) * 0.05
    Bx = -(B * (1.0 - np.abs(eps)))

    times = [
        (t0 + timedelta(seconds=int(i * 45 + rng.integers(0, 6))))
        .strftime("%Y.%m.%dT%H:%M:%S")
        for i in range(len(B))
    ]

    df = pd.DataFrame(
        {
            "time stamp": times,
            "x": pts[:, 0],
            "y": pts[:, 1],
            "z": pts[:, 2],
            "Bx": np.round(Bx, 9),
            "B": np.round(B, 9),
        }
    )

    # summary footer like the real exports
    ppm = (B.max() - B.min()) / B.mean() * 1e6
    footer = pd.DataFrame(
        {
            "time stamp": ["maximum", "minimum", "average", "ppm", ""],
            "x": [np.nan] * 5,
            "y": [np.nan] * 5,
            "z": [np.nan] * 5,
            "Bx": [Bx.min(), Bx.max(), Bx.mean(), np.nan, np.nan],
            "B": [
                B.max(),
                B.min(),
                B.mean(),
                round(ppm, 2),
                f"{B.mean() * GAMMA:.2f} MHz",
            ],
        }
    )

    name = f"{scanner}_DSV{dsv}_RES{res}_S{scan:02d}.xlsx"
    pd.concat([df, footer], ignore_index=True).to_excel(OUT / name, index=False)
    print(f"{name:38s} {len(B):5d} pts   mean {B.mean()*1e3:7.3f} mT   "
          f"pp {ppm:8.1f} ppm")


def main():
    OUT.mkdir(exist_ok=True)
    jobs = [
        # scanner    dsv  res scan  B0     drift  noise  start time
        ("NEOSCAN",   100, 10, 1, 0.0480,    0.0,  8.0, datetime(2026, 6, 1, 9, 12)),
        ("NEOSCAN",   100, 10, 2, 0.0480,  -85.0,  8.0, datetime(2026, 6, 1, 14, 3)),
        ("NEOSCAN",   100,  5, 1, 0.0480,  -40.0,  8.0, datetime(2026, 6, 2, 8, 41)),
        ("MOUSEMAG",   30,  4, 1, 0.0720,    0.0,  5.0, datetime(2026, 6, 8, 10, 5)),
        ("MOUSEMAG",   30,  4, 2, 0.0720,   60.0,  5.0, datetime(2026, 6, 8, 13, 27)),
        ("HALBACH64", 140, 14, 1, 0.0462,    0.0, 10.0, datetime(2026, 6, 15, 9, 55)),
        ("HALBACH64", 140, 14, 2, 0.0462, -120.0, 10.0, datetime(2026, 6, 16, 9, 48)),
        ("PORTABLE",   80,  8, 1, 0.0641,    0.0,  9.0, datetime(2026, 6, 22, 11, 19)),
        ("KIDSCAN",   120, 12, 1, 0.0550,    0.0,  9.0, datetime(2026, 6, 25, 15, 2)),
        ("BENCHTOP",   20,  3, 1, 0.0985,    0.0,  4.0, datetime(2026, 6, 29, 16, 44)),
    ]
    for i, (sc, dsv, res, scan, b0, drift, noise, t0) in enumerate(jobs):
        make_file(sc, dsv, res, scan, b0, drift, noise, t0, seed=1000 + i)


if __name__ == "__main__":
    main()
