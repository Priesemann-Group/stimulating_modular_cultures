import os
import numpy as np
from itertools import product

# set directory to the location of this script file to use relative paths
os.chdir(os.path.dirname(__file__))

# seed for rank 0, will increase per thread
seed = 25_000

# parameters to scan, noise rate, ampa strength, and a few repetitons for statistics
l_topo = ['2x2merged', '2x2_fixed']
l_rate = np.array([20, 25, 30, 35, 37, 38, 39, 40])
l_gampa = np.array([15, 40, 45, 50,
    ] + list(np.arange(20, 37) ))
l_recovery = np.array([2.0])
l_alpha = np.array([0.005 , 0.0075, 0.01  , 0.0125])
l_rep = range(0, 3)

arg_list = product(l_topo, l_rate, l_gampa, l_recovery, l_alpha, l_rep)

# we need to create the topology first for every seed!

count = 0
with open("./parameters_topo.tsv", "w") as f_topo:
    with open("./parameters_dyn.tsv", "w") as f_dyn:

        # set the cli arguments
        f_topo.write("# commands to create topology\n")
        f_dyn.write("# commands to run dynamics on existing topology\n")

        for i in arg_list:
            topo = i[0]
            rate = i[1]
            gampa = i[2]
            recovery = i[3]
            alpha  = i[4]
            rep  = i[5]
            topo_path = f"./dat/topo/{topo}/gampa={gampa:04.2f}_rate={rate:04.2f}_recovery={recovery:04.2f}_alpha={alpha:.04f}_rep={rep:02d}.hdf5"
            dyn_path = f"./dat/dyn/{topo}/gampa={gampa:04.2f}_rate={rate:04.2f}_recovery={recovery:04.2f}_alpha={alpha:.04f}_rep={rep:02d}.hdf5"

            f_topo.write(
                # topology command
                f"/data.nst/share/projects/paul_brian_modular_cultures/topology_orlandi_standalone/exe/orlandi_standalone -N 100 -s {seed:d} -o {topo_path} -f {topo} -a {alpha} -a_weighted 1\n"
            )
            f_dyn.write(
                # dynamic command
                f"python ./src/ibi.py -i {topo_path} " +
                f"-o {dyn_path} " +
                f"-d 3600 -equil 300 -s {seed:d} " +
                f"-gA {gampa:04.2f} -tD {recovery:04.2f} -r {rate:04.2f}\n"
            )

            seed += 1
            count += 1


print(f"number of argument combinations: {count}")
