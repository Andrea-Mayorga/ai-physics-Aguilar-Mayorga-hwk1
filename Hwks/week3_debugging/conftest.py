"""Shared pytest fixtures for the Week 3 oscillator test suite.

The module under test is chosen with the environment variable OSC_MODULE:

    OSC_MODULE=ai_generated_oscillator_original python -m pytest -v   # buggy
    python -m pytest -v                                               # fixed (default)
"""
import importlib
import os
import sys

import matplotlib

matplotlib.use("Agg")  # draw figures off-screen: no windows pop up during tests

import matplotlib.pyplot as plt
import numpy as np
import pytest

# Make sure the folder that contains this file (and the oscillator scripts) is importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def osc():
    """Import the oscillator module named by OSC_MODULE (fixed version by default)."""
    name = os.environ.get("OSC_MODULE", "ai_generated_oscillator_fixed")
    return importlib.import_module(name)


@pytest.fixture(scope="session")
def x_grid():
    """Fine, wide grid for integrals: psi_n decays like exp(-x^2/2), so |x| <= 12 is effectively infinite."""
    return np.linspace(-12.0, 12.0, 4001)


@pytest.fixture
def plotted_lines(osc, monkeypatch):
    """Run osc.main() with plt.show() disabled and return the Line2D objects it drew."""
    plt.close("all")
    monkeypatch.setattr(plt, "show", lambda *args, **kwargs: None)
    osc.main()
    lines = plt.gca().get_lines()
    yield lines
    plt.close("all")
