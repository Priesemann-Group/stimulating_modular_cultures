# ------------------------------------------------------------------------------ #
# @Author:        Victor Buendia Ruiz-Azuaga
# @Email:         vbuendiar@onsager.ugr.es
# ------------------------------------------------------------------------------ #

from genericpath import exists
import numpy as np
import pandas as pd
import os
from numba import jit



def gate_deactivation_function(src_resources):
    """
    Auxiliar implementation of the response function of the gate to the number of resources. For plotting purposes only.

    #Parameters:
    src_resources: ndarray
        Returns the response function of the given array
    """
    def f2(inpt, thrs, gamma, lmbda):
        return lmbda / (1.0 + np.exp(-gamma * (inpt - thrs)))

    dt = 0.01
    prob = 1.0 - np.exp(
        -dt * (1.0 - f2(src_resources, 0.5, 40.0, 1.0))
    )

    return prob

def simulate_model(
    tf,
    output_filename,
    no_gates    = False,
    m0          = 2.0,
    tc          = 45.0,
    td          = 15.0,
    b           = 1.55,
    sigma       = 0.1,
    basefiring  = 0.01,
    w0          = 0.3,
    lamb        = 1.0,
    g           = 0.7,
    ext_str     = 1.5,
    ksig        = 1.6,
    basethr     = 0.4,
    gain        = 10.0,
    gatethr     = 0.5,
    kgate       = 40.0,
    dt          = 0.01,
    rseed       = None 
):
    """
    Simulate the mesoscopic model up to time tf, with the given parameters. 

    #Parameters:
    tf : float
        When does the simulation end.
    output_filename : str
        Name of the file that will be stored in disk, as output_filename.csv.    
    
    no_gates : bool, optional
        Control whether gates are active. If False (default), the gates are used.
    
    m : float, optional
        Maximum amount of synaptic resources. 
    
    tc : float, optional
        Timescale of synaptical resource charging
    td : float, optional
        Timescale of synaptical resource discharge

    b : float, optional
        Timescale of activity exponential decay
    
    sigma : float, optional
        Strenght of background noise fluctuations
    
    basefiring : float, optional
        Firing rate in absence of stimulation.
    
    w0 : float, optional
        Coupling strenght between different nodes
    
    lamb : float, optional
        Rate of gate becoming inactive, thus not letting activity go through
    g : float, optional
        Rate of gate recovery
    
    ext_str : float, optional
        Stimulation strength
    
    basethr : float, optional
        Threshold for the non-linear sigmoidal function. Any activity which falls below this value will not affect the module
    gain : float, optional
        Gain that multiplies the result of the sigmoidal function, thus increasing the effect of the input

    gatethr : float, optional
        Threshold of activity needed in order to be able to affect the gate. Levels of activity below cannot inactivate a gate.
    kgate : float, optional
        Slope of the gate's response sigmoid

    dt_ : float, optional
        Timestep of the Euler integrator (default=0.01)
    
    rseed : float, optional
        Use a custom random seed to ensure reproducitibility. If None (default), will use whatever Numpy selects 

    """

    #Set random seed
    if rseed != None:
        np.random.seed(rseed)

    # Stochastic dt
    sqdt = np.sqrt(dt)

    # Binnings associated to such a time 
    nt = int(tf / dt)

    # Initialize variables
    x = np.empty((4, nt))     #activity
    mvar = np.empty((4, nt))  #resources
    gate = np.ones((4, 4), dtype=int)  # state of each gate at this time (directed) gate[from, to]


    # Model parameters!
    basefiring = np.ones(4) * basefiring  # Minimum (small) firing rate

    # Coupling matrix
    w = np.zeros((4, 4), dtype=int)  # Adjacency matrix
    w[0, 1] = 1
    w[1, 0] = 1
    w[0, 2] = 1
    w[2, 0] = 1
    w[1, 3] = 1
    w[3, 1] = 1
    w[2, 3] = 1
    w[3, 2] = 1

    #lamb = lamb   # Gate open timescale
    #g = g   # Gate recovery
    g = g / tc

    # External input
    ext_input = np.ones(4) * ext_str

    # Sigmoid definition (Wilson-Cowan type, such that f(x<=0)=0 and f(+infty)=gain)
    thrsig = np.exp(ksig * basethr)  # Shortcut to make computation faster

    def f(inpt):
        expinpt = np.exp(-ksig * (inpt - basethr))
        return (
            gain * (1.0 - expinpt) / (thrsig * expinpt + 1.0) if inpt >= basethr else 0.0
        )

    #Sigmoid for gate response
    def gate_sigm(inpt, thrs, gamma, lmbda):
        return lmbda / (1.0 + np.exp(-gamma * (inpt - thrs)))

    # Initialize parameters to spontaneous, get initial value of resources
    m = np.ones(4) * m0

    mvar[:, 0] = np.random.rand(4) * m0
    x[:, 0] = np.random.rand(4) 

    # Define some auxiliary constants for gates
    GATE_OPEN = 0
    GATE_CLOSED = 1

    # -------------
    # Simulation
    # -------------

    # Main computation loop: Milstein algorithm, assuming Ito interpretation
    t = 0.0
    for j in range(nt - 1):

        # Update each cluster
        old_gate = gate.copy()
        for c in range(4):

            suma = 0.0
            # Interaction with other connected clusters (usually one keeps a list of neighbours, etc. but we only have 4 clusters...)
            for neigh in range(4):
                if w[neigh, c] > 0.0:

                    #Sum input to cluster c, only through open gates
                    suma += (
                        ((old_gate[neigh, c] == GATE_OPEN) or no_gates) * w0 * x[neigh, j]
                    )

                    # Close door depending on activity of source
                    if old_gate[c, neigh] == GATE_OPEN:
                        prob = 1.0 - np.exp(
                            -dt * (1.0 - gate_sigm(mvar[c, j], gatethr, kgate, lamb))
                        )
                        ranumb = np.random.rand()
                        if ranumb < prob:
                            gate[c, neigh] = GATE_CLOSED
                    # Open door with a characteristic time
                    else:
                        prob = 1.0 - np.exp(-dt * g)
                        if np.random.rand() < prob:
                            gate[c, neigh] = GATE_OPEN
            suma *= 0.5

            # Multiplicative noise (+ extra additive)
            noise = np.random.standard_normal() * sigma
            if x[c, j] > basefiring[c]:
                noise += np.sqrt(x[c, j]) * np.random.standard_normal() * sigma

            # Terms for the deterministic system
            t1 = b * (x[c, j] - basefiring[c])  # Spontaneous decay to small firing
            #t2 = (1.0 - x[c,j]) * f(mvar[c, j] * (x[c, j] + suma + ext_input[c]))  # Input to the cluster
            t2 = f(mvar[c, j] * (x[c, j] + suma + ext_input[c]))  # Input to the cluster

            # Update our variables
            x[c, j + 1] = x[c, j] + dt * (-t1 + t2) + sqdt * noise
            mvar[c, j + 1] = mvar[c, j] + dt * (
                (m[c] - mvar[c, j]) / tc - mvar[c, j] * x[c, j] / td
            )

        t += dt  # Update the time

    # ------------
    # Output
    # -----------
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)

    # Create a DataFrame easy to read in our workflow and export as HDF
    df = pd.DataFrame(columns=["time"] + [f"mod_{m_cd}" for m_cd in range(1, 5)])
    df["time"] = np.arange(0, tf, dt)
    for m_cd in range(4):
        df[f"mod_{m_cd+1}"] = x[m_cd, :]
        df[f"mod_{m_cd+1}_res"] = mvar[m_cd, :]
    df.to_hdf(f"{output_filename}.hdf5", f"/dataframe", complevel=9)
