"""
1D Quantum Harmonic Oscillator
------------------------------
Computes the first five energy levels and plots the corresponding
probability densities |psi_n(x)|^2 for n = 0, 1, 2, 3, 4.

Dimensionless units are used by default:
    hbar = m = omega = 1

The module can also be imported as AI_test_driven_oscillator.
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.special import eval_hermite, factorial


# ---------------------------------------------------------------------
# Physical constants and configuration
# ---------------------------------------------------------------------

HBAR = 1.0
MASS = 1.0
OMEGA = 1.0

N_LEVELS = 5


# ---------------------------------------------------------------------
# Energy eigenvalues
# ---------------------------------------------------------------------

def energy_levels(hbar=HBAR, omega=OMEGA):
    """
    Calculate the first five energy eigenvalues of the 1D
    quantum harmonic oscillator.

    Parameters
    ----------
    hbar : float
        Reduced Planck constant.
    omega : float
        Angular frequency of the oscillator.

    Returns
    -------
    numpy.ndarray
        Energy eigenvalues E_n = hbar * omega * (n + 1/2).
    """
    n = np.arange(N_LEVELS)
    return hbar * omega * (n + 0.5)


# ---------------------------------------------------------------------
# Harmonic oscillator eigenstates
# ---------------------------------------------------------------------

def harmonic_state(n, x, hbar=HBAR, mass=MASS, omega=OMEGA):
    """
    Evaluate the normalized nth eigenstate of the 1D quantum
    harmonic oscillator.

    The normalized wavefunction is

        psi_n(x) = (1 / sqrt(2^n n!))
                   * (m*omega / (pi*hbar))^(1/4)
                   * H_n(xi)
                   * exp(-xi^2 / 2)

    where

        xi = sqrt(m*omega / hbar) * x

    and H_n is the physicists' Hermite polynomial.

    Parameters
    ----------
    n : int
        Quantum number (n >= 0).
    x : array_like
        Spatial coordinates.
    hbar : float
        Reduced Planck constant.
    mass : float
        Particle mass.
    omega : float
        Angular frequency.

    Returns
    -------
    numpy.ndarray
        Normalized wavefunction evaluated at x.
    """
    if not isinstance(n, (int, np.integer)) or n < 0:
        raise ValueError("The quantum number n must be a non-negative integer.")

    if hbar <= 0 or mass <= 0 or omega <= 0:
        raise ValueError("hbar, mass, and omega must be positive.")

    x = np.asarray(x, dtype=float)

    # Dimensionless position coordinate
    xi = np.sqrt(mass * omega / hbar) * x

    # Physicists' Hermite polynomial H_n(xi)
    hermite = eval_hermite(n, xi)

    # Normalization constant
    normalization = (
        (mass * omega / (np.pi * hbar)) ** 0.25
        / np.sqrt((2.0 ** n) * factorial(n))
    )

    # Normalized eigenfunction
    psi = normalization * hermite * np.exp(-xi**2 / 2.0)

    return psi


# ---------------------------------------------------------------------
# Probability densities and plotting
# ---------------------------------------------------------------------

def main():
    """
    Compute and plot the probability densities of the first five
    harmonic oscillator eigenstates.
    """

    # Spatial grid
    x = np.linspace(-5.0, 5.0, 1000)

    # Energy eigenvalues
    energies = energy_levels()

    print("1D Quantum Harmonic Oscillator")
    print("--------------------------------")
    print("Energy eigenvalues (dimensionless units):")

    for n, energy in enumerate(energies):
        print(f"E_{n} = {energy:.6f}")

    # Plot probability densities
    plt.figure(figsize=(9, 6))

    for n in range(N_LEVELS):
        psi = harmonic_state(n, x)

        # Probability density
        probability_density = np.abs(psi) ** 2

        plt.plot(
            x,
            probability_density,
            label=f"n={n}"
        )

    plt.xlabel("Position x")
    plt.ylabel(r"Probability density $|\psi_n(x)|^2$")
    plt.title("1D Quantum Harmonic Oscillator")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    plt.show()


# ---------------------------------------------------------------------
# Script entry point
# ---------------------------------------------------------------------

if __name__ == "__main__":
    main()
