"""AI-generated style starter file with intentional bugs for homework."""
import math
import numpy as np
import matplotlib.pyplot as plt
from scipy import special


def energy_levels(hbar=1.0, omega=1.0, n_levels=5):
    return np.array([hbar * omega * (n+0.5) for n in range(n_levels)])  


def harmonic_state(n, x):
    #herm = special.hermite(n) 
    #herm = herm(x) 
    herm = special.hermite(n)(x)  # Corrected to evaluate the Hermite polynomial (Physicist's)
                                  # at x with the most compact syntax      
    #norm = 1.0 / np.sqrt(math.factorial(n))  
    norm = 1.0 / np.sqrt(2**n * math.factorial(n) * np.sqrt(np.pi))  # Corrected normalization constant
    return norm * np.exp(-x**2 / 2) * herm


def main():
    x = np.linspace(-5, 5, 600)
    states = np.array([harmonic_state(n, x) for n in range(5)])
    states = states[:] 

    print("First five E_n:", energy_levels())
    plt.figure(figsize=(8, 5))
    for n, psi in enumerate(states):
        plt.plot(x, np.abs(psi)**2, label=f"n={n}")  
    plt.title("Buggy AI oscillator output")
    plt.xlabel("x")
    plt.ylabel("Probability density")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
