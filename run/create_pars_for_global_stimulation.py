# ------------------------------------------------------------------------------ #
# @Author:        F. Paul Spitzner
# @Email:         paul.spitzner@ds.mpg.de
# @Created:       2022-06-22 10:12:19
# @Last Modified: 2022-11-23 16:27:12
# ------------------------------------------------------------------------------ #
# This creates a `parameter.tsv` where each line contains one parameter set,
# which can be directly called from the command line (i.e. on a cluster).
# * Here: parameters for stimulation to all modules
# * output file names have the form
#   `stim=off_k=-1_jA=45.0_jG=50.0_jM=15.0_tD=20.0_rate=80.0_rep=001.hdf5`
#   where `stim=off` means that no modules are targeted in addition to the base
#   rate (80.)
# * the sweep is done over increasing `rate= ...`
# ------------------------------------------------------------------------------ #

import os
import numpy as np
from itertools import product

# set directory to the location of this script file to use relative paths
os.chdir(os.path.dirname(__file__))
out_path = os.path.abspath("/scratch01.local/pspitzner/revision_1/simulations/lif/raw_alpha")
print(f"simulation results will go to {out_path}")

# seed for rank 0, will increase per thread
seed = 6_000

# parameters to scan, noise rate, ampa strength, and a few repetitons for statistics
kin=25
l_k_inter = np.array([-1, 0, 1, 3, 5, 10, 20])
l_mod = np.array(["off"])
l_rep = np.arange(0, 50)
l_jA = [45.0]
l_jG = [50.0]
l_jM = [15.0]
l_tD = [20.0]
l_rate = np.arange(65, 111, 5)

print("l_jA  ", l_jA)
print("l_jG  ", l_jG)
print("l_jM  ", l_jM)
print("l_tD  ", l_tD)
print("l_rate", l_rate)

bridge_weight = 1.0
inh_frac = 0.20

arg_list = product(l_k_inter, l_jA, l_jG, l_jM, l_tD, l_rep)

count_dynamic = 0
count_topo = 0
with open("./parameters.tsv", "w") as f_dyn:
    # set the cli arguments
    f_dyn.write("# commands to run, one line per realization\n")

    for args in arg_list:
        k_inter = args[0]
        jA = args[1]
        jG = args[2]
        jM = args[3]
        tD = args[4]
        rep = args[-1]
        mod = l_mod[0]

        seed += 1

        # same seeds for all rates so that topo matches
        for rate in l_rate:
            f_base = f"k={k_inter:d}_kin={kin:02d}_jA={jA:.1f}_jG={jG:.1f}_jM={jM:.1f}_tD={tD:.1f}_rate={rate:.1f}_rep={rep:03d}.hdf5"

            dyn_path = f"{out_path}/stim={mod}_{f_base}"

            if mod == "off":
                stim_arg = ""
            else:
                stim_arg = f"-stim hideaki -mod {mod}"

            f_dyn.write(
                # dynamic command
                f"python ./src/quadratic_integrate_and_fire.py "
                + f'-o {dyn_path} '
                + f'-kin {kin} '
                + f"-k {k_inter} "
                + f"-d 1800 -equil 300 -s {seed:d} "
                + f"--bridge_weight {bridge_weight} "
                + f"--inhibition {inh_frac} "
                + f"-jA {jA} -jG {jG} -jM {jM} -r {rate} -tD {tD} "
                + f"{stim_arg}\n"
            )

            count_dynamic += 1

print(f"number of argument combinations for dynamics: {count_dynamic}")
