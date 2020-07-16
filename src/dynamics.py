# ------------------------------------------------------------------------------ #
# @Author:        F. Paul Spitzner
# @Email:         paul.spitzner@ds.mpg.de
# @Created:       2020-02-20 09:35:48
# @Last Modified: 2020-03-04 13:53:21
# ------------------------------------------------------------------------------ #
# Dynamics described in Orlandi et al. 2013, DOI: 10.1038/nphys2686
# Loads topology from hdf5 or csv and runs the simulations in brian.
# ------------------------------------------------------------------------------ #

import os
import sys
import glob
import h5py
import argparse

import numpy as np
from brian2 import *

# ------------------------------------------------------------------------------ #
# model parameters
# ------------------------------------------------------------------------------ #

# fmt: off
# membrane potentials
vr = -60 * mV  # resting potential, neuron relaxes towards this without stimulation
vt = -45 * mV  # threshold potential
vp =  35 * mV  # peak potential, after vt is passed, rapid growth towards this
vc = -50 * mV  # reset potential

# soma
tc = 50 * ms  # time scale of membrane potential
ta = 50 * ms  # time scale of inhibitory current u

k = 0.5 / mV  # resistance over capacity(?), rescaled
b = 0.5       # sensitivity to sub-threshold fluctuations
d =  50 * mV  # after-spike reset of inhibitory current u

# synapse
tD =   1 * second  # characteristic recovery time, between 0.5 and 20 seconds
tA =  10 * ms      # decay time of post-synaptic current (AMPA current decay time)
gA =  50 * mV      # AMPA current strength, between 10 - 50 mV

# noise
beta = 0.8         # D = beta*D after spike, to reduce efficacy, beta < 1
rate = 0.03 / ms   # rate for the poisson input (shot-noise), between 0.01 - 0.05 1/ms
gm =  25 * mV      # shot noise (minis) strength, between 10 - 50 mV
gs = 300 * mV * mV * ms * ms  # white noise strength, via xi = dt**.5 * randn()
# fmt:on

defaultclock.dt = 0.05 * ms

# ------------------------------------------------------------------------------ #
# helper
# ------------------------------------------------------------------------------ #


def h5_load(filename, dsetname, raise_ex=True):
    try:
        file = h5py.File(filename, "r")
        res = file[dsetname][:]
        file.close()
        return res
    except Exception as e:
        print(f"failed to load {dsetname} from {filename}")
        if raise_ex:
            raise e
        else:
            return np.nan


def visualise_connectivity(S):
    Ns = len(S.source)
    Nt = len(S.target)
    figure(figsize=(10, 4))
    subplot(121)
    plot(zeros(Ns), arange(Ns), "ok", ms=10)
    plot(ones(Nt), arange(Nt), "ok", ms=10)
    for i, j in zip(S.i, S.j):
        plot([0, 1], [i, j], "-k", lw=0.1)
    xticks([0, 1], ["Source", "Target"])
    ylabel("Neuron index")
    xlim(-0.1, 1.1)
    ylim(-1, max(Ns, Nt))
    subplot(122)
    plot(S.i, S.j, "ok")
    xlim(-1, Ns)
    ylim(-1, Nt)
    xlabel("Source neuron index")
    ylabel("Target neuron index")


# ------------------------------------------------------------------------------ #
# command line arguments
# ------------------------------------------------------------------------------ #

parser = argparse.ArgumentParser(description="Brian")
parser.add_argument("-i", dest="input_path", help="input path", metavar="FILE")
parser.add_argument("-o", dest="output_path", help="output path", metavar="FILE")
parser.add_argument("-s", dest="seed", default=117, help="rng", type=int)
args = parser.parse_args()

print(f"seed: {args.seed}")
numpy.random.seed(args.seed)

try:
    # load from hdf5
    a_ij = h5_load(args.input_path, "/data/connectivity_matrix")
    num_n = int(h5_load(args.input_path, "/meta/topology_num_neur"))
    mod_ids = h5_load(args.input_path, "/data/neuron_module_id")
    mod_sorted = np.argsort(mod_ids)
except:
    # or a csv
    try:
        a_ij = loadtxt(args.input_path)
        num_n = a_ij.shape[0]
    except:
        print("Unable to load toplogy from {args.input_path}")

# ------------------------------------------------------------------------------ #
# model
# ------------------------------------------------------------------------------ #

G = NeuronGroup(
    N=num_n,
    model="""
        dv/dt = ( k*(v-vr)*(v-vt) -u +I            # [6] soma potential
                +xi*(gs/tc)**0.5 )/tc   : volt     # white noise term
        dI/dt = -I/tA                   : volt     # [9, 10]
        du/dt = ( b*(v-vr) -u )/ta      : volt     # [7] inhibitory current
        dD/dt = ( 1-D )/tD              : 1        # [11] recovery to one
    """,
    threshold="v > vp",
    reset="""
        v = vc           # [8]
        u = u + d        # [8]
        D = D * beta     # [11] delta-function term on spike
    """,
    method="euler",
)

S = Synapses(
    source=G,
    target=G,
    on_pre="""
        I_post += D_pre * gA    # [10]
    """,
)

# shot-noise:
# by targeting I with poisson, we should get pretty close to javiers version.
# here, N=1 is input per neuron
mini_g = PoissonInput(target=G, target_var="I", N=1, rate=rate, weight=gm)

# connect synapses from loaded matrix or randomly
try:
    pre, post = np.where(a_ij == 1)
    for idx, i in enumerate(pre):
        j = post[idx]
        # group modules close to each other
        i = np.argwhere(mod_sorted == i)[0, 0]
        j = np.argwhere(mod_sorted == j)[0, 0]
        S.connect(i=i, j=j)
except:
    print(f"Creating Synapses randomly")
    S.connect(condition="i != j", p=0.1)

# initalize to a somewhat sensible state. we could have different neuron types
G.v = "vc + 5*mV*rand()"

# equilibrate
run(10 * second, report="stdout")

# ------------------------------------------------------------------------------ #
# Running and Plotting
# ------------------------------------------------------------------------------ #

# disable state monitors that are not needed for production
stat_m = StateMonitor(G, ["v", "I", "u", "D"], record=True)
spks_m = SpikeMonitor(G)
# mini_m = SpikeMonitor(mini_g)

run(30 * second, report="stdout")

ion()  # interactive plotting
fig, ax = subplots(4, 1, sharex=True)

n1 = randint(0, num_n)  # some neuron to highlight
sel = where(spks_m.i == n1)[0]

# ax[0].plot(mini_m.t / second, mini_m.i, ".y")
ax[0].plot(spks_m.t / second, spks_m.i, ".k")
ax[0].plot(spks_m.t[sel] / second, spks_m.i[sel], ".")
ax[0].set_ylabel("Neuron index")
ax[0].set_title(f"{args.input_path}")


ax[1].plot(stat_m.t / second, stat_m.v[n1], label=f"Neuron {n1}")
ax[1].set_ylabel("v")
ax[1].legend()

ax[2].plot(stat_m.t / second, stat_m.u[n1], label=f"Neuron {n1}")
ax[2].set_ylabel("u")

ax[3].plot(stat_m.t / second, stat_m.D[n1], label=f"Neuron {n1}")
ax[3].set_xlabel("Time (s)")
ax[3].set_ylabel("D")
ax[3].legend()

show()