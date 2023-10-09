# Stimulating Modular Cultures

## Published Article

- [arxiv: 2205.10563](https://arxiv.org/abs/2205.10563)
- [science advances](https://www.science.org/doi/10.1126/sciadv.ade1755)

```bibtex
@article{yamamoto_modular_2023,
  title = {Modular Architecture Facilitates Noise-Driven Control of Synchrony in Neuronal Networks},
  author = {Yamamoto, Hideaki and Spitzner, F. Paul and Takemuro, Taiki and Buend{\'i}a, Victor and Murota, Hakuba and Morante, Carla and Konno, Tomohiro and Sato, Shigeo and {Hirano-Iwata}, Ayumi and Levina, Anna and Priesemann, Viola and Mu{\~n}oz, Miguel A. and Zierenberg, Johannes and Soriano, Jordi},
  year = {2023},
  month = aug,
  journal = {Science Advances},
  volume = {9},
  eprint = {2205.10563},
  pages = {eade1755},
  doi = {10.1126/sciadv.ade1755},
}
```

## Data

Raw data, preprocessed recordings and rendered movies can be downloaded [here](https://gin.g-node.org/pspitzner/stimulating_modular_cultures)
(Note: experimental data will be published after acceptance.)

## Dependencies

All dependencies should be installed automatically if you create a new conda environment from the repository directory.
```bash
conda env create --file environment.yml
conda activate modular_cultures
```

## Getting started
We provide [interactive notebooks](notebooks) which serve as a good starting point, they showcase the models and link which parts of the code lead to which plot.
(Note: refactoring of backed for Revision 1 needed)


## Code structure
The repo is structured into folders as follows:

- [`src/`](src) contains the models for all simulations. In particular:
    - Merged and modular [topologies](src/topology.py) using axon growth algorithm proposed by Orlandi et al.
    - Leaky integrate and fire [neuron dynamics](src/quadratic_integrate_and_fire.py) that run in [Brian2](https://brian2.readthedocs.io/en/stable/) to generate artificial spiking data.
    - The [mesoscopic model](src/mesoscopic_model.py) where modules are treated as the smallest spacial unit.

- [`run/`](run) contains helpers to run the simulations from `src` on a cluster, and to create parameter combinations / sweeps that can be computed in serial.

- [`ana/`](ana) contains all post-processing. Frontmost:
    - [`paper_plots.py`](ana/paper_plots.py) is the high-level wrapper that creates our figures.
    - [`process_conditions.py`](ana/process_conditions.py) analyses the raw spiking data from either experiments or simulations to create before-after comparisons
    - [`ndim_merge.py`](ana/ndim_merge.py) analyses simulation data, sweeping different input strength.
    - [`ana_helper.py`](ana/ana_helper.py) contains all the low-level analysis functions that operate on spike times, importers of simulation and experimental data and much more.
        * All analysis work on a nested dictionary, mostly  called `h5f`. Each of those corresponds to one trial, and we attach all analysis results to this dict.
        * The idea is that later functions (such as plotting) can use previous results. Note that this is done live, and that although we "add" to the dictionaries, nothing is written to disk.
    - [`plot_helper.py`](ana/plot_helper.py) provides various functions that take such a `h5f` dict and plot some aspect of it with consistent styling. Examples include timeseries, rasters, and distributions.
