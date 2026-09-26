"""track-atlas shared library."""
import os

# The matrices here are small (racing-line QP ~1-2k); multi-threaded BLAS only
# adds contention, and on a busy machine made one solve ~80x slower.
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")
