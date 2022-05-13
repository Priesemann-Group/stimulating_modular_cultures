import numpy as np
import plot_helper as ph
import ana_helper as ah
import seaborn as sns
import re
import glob
import logging

log = logging.getLogger(__name__)
log.setLevel("INFO")

# import those last, so that the matpllotlb rc params are not overwritten
# they are tweaked for movies, dark background, agg backened, etc
from movie_business import matplotlib, plt
from movie_business import MovieWriter
from movie_business import FadingLineRenderer, MovingWindowRenderer, TextRenderer
from movie_business import TopologyRenderer


def main():

    # experiments, place the mp4s next to the hdf5s...
    candidates = glob.glob("./dat/exp_out/**/**/*.hdf5")
    for input_path in candidates:
        regex = re.search("exp_out/(.*?)/(.*?)/", input_path, re.IGNORECASE)
        title = regex.groups()[0] + "\n" + regex.groups()[1]
        log.info("\n" + title + "\n")
        # continue
        make_a_movie(
            input_path=input_path,
            input_type="experiment",
            title=title,
            output_path=input_path.replace(".hdf5", ".mp4"),
            movie_duration=53.1,
            tbeg=0,
            tend=540,
        )

    # simulations
    # for k in [1, 5, 10, -1]:
    for k in [-1]:
        for noise in [80, 90]:
            title = f"k={k}, {noise}Hz"
            if k == -1:
                title = f"merged, {noise}Hz"
            log.info("\n" + title + "\n")

            make_a_movie(
                input_path=f"./dat/the_last_one/dyn/highres_stim=off_k={k}_jA=45.0_jG=50.0_jM=15.0_tD=20.0_rate={noise}.0_rep=001.hdf5",
                input_type="simulation",
                title=title,
                output_path=f"./mov/{title.replace(', ', '_')}.mp4",
                tbeg=0,
                tend=610,
                movie_duration=60,
            )


def make_a_movie(
    input_path,
    output_path="./mov/simulation_test.mp4",
    input_type="simulation",
    title=None,
    show_time=False,
    movie_duration=60,
    window_from=-20,
    window_to=100,
    tbeg=0,
    tend=610,
    only_test_layout=False,
):
    """
    Wrapper to create the layout used for movies of simulions.

    Here we do the data analysis in place, using default parameters.
    (For Experiments we use the analyzed files coming out of process_conditions.)

    # Parameters
    input_path: str
        Path to the HDF5 file containing the simulation data.
    input_type: str
        Either "simulation" or "experiment", we need to tweak some settings.
    output_path: str
        Path to the output movie file.
    movie_duration: float
        Duration of the movie in seconds.
    window_from, to: float
        Start, end of the time window showing the data, in data units.
    tbeg, tend: float
        Start, end time of the data, in data units.
    only_test_layout: bool
        Use this to test the layout without actually creating a movie.
    """

    # keep a list of renderers that will be updated in the writers render loop.
    # every renderer needs to have a function `set_time` that takes the experimental
    # timestamp as input.
    writer = MovieWriter(
        output_path=output_path,
        movie_duration=movie_duration,
        tbeg=tbeg,
        tend=tend,
    )

    # I like to set the decay time propto movie playback speed
    time_ratio = writer.movie_duration / (writer.tend - writer.tbeg)
    decay_time = 0.5 / time_ratio

    # ------------------------------------------------------------------------------ #
    # Figure layout
    # ------------------------------------------------------------------------------ #

    fig = plt.figure(figsize=(1920 / 300, 800 / 300), dpi=300)
    fig.patch.set_facecolor("black")
    gs = fig.add_gridspec(
        nrows=2,
        ncols=4,
        # use one dummy column for the axis ticks
        width_ratios=[0.4, 0.6 * 0.333, 0.07, 0.6 * 0.666],
        height_ratios=[0.6, 0.4],
        wspace=0.02,
        hspace=0.2,
        left=0.01,
        right=0.99,
        top=0.95,
        bottom=0.15,
    )

    # ------------------------------------------------------------------------------ #
    # Topology plot
    # ------------------------------------------------------------------------------ #

    ax = fig.add_subplot(gs[:, 0])
    tpr = TopologyRenderer(input_path=input_path, ax=ax)
    tpr.decay_time = decay_time

    ax.set_xlim(-40, 640)
    ax.set_ylim(-40, 640)
    if "k=-1" in input_path:
        # align merged guys differently
        ax.set_xlim(-140, 540)
        ax.set_ylim(-140, 540)
    ax.set_clip_on(False)
    writer.renderers.append(tpr)

    # ------------------------------------------------------------------------------ #
    # population activity plot
    # ------------------------------------------------------------------------------ #

    ax = fig.add_subplot(gs[1, 3])
    h5f = ah.prepare_file(input_path)
    ah.find_rates(h5f)

    ph.plot_module_rates(h5f=h5f, ax=ax, alpha=0.5)
    ph.plot_system_rate(h5f=h5f, ax=ax, color="white")
    ax.get_legend().set_visible(False)
    ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(30.0))
    ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlabel("Time (seconds)")
    ax.set_ylabel("")

    if input_type == "simulation":
        ax.set_ylim(-15, 150)
        sns.despine(ax=ax, right=True, top=True, bottom=True, left=True, offset=1)
        ax.yaxis.set_visible(False)
        ax.tick_params(left=False, labelleft=False, bottom=False)
    else:
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(15))
        ax.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(10))
        ax.set_ylim(-3, 30)
        sns.despine(
            ax=ax,
            right=True,
            top=True,
            bottom=True,
            left=False,
            offset={"bottom": 1, "left": 8},
            trim=True,
        )
        # workaround for despine
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(30))
        ax.tick_params(left=True, labelleft=True, bottom=False)

    # get a axis relative position in data cordinates
    axis_to_data = ax.transAxes + ax.transData.inverted()
    ti_y_pos = -0.0
    ti_y_pos = axis_to_data.transform([1, ti_y_pos])[1]
    ti = ax.plot([0], [ti_y_pos], marker="^", markersize=3, color="white", clip_on=False)[
        0
    ]

    writer.renderers.append(
        MovingWindowRenderer(
            ax=ax,
            tbeg=writer.tbeg,
            tend=writer.tend,
            # this plot only has 2/3 the width of the raster
            window_from=window_from,
            window_to=window_from + (window_to - window_from),
            time_indicator=ti.set_xdata,
        )
    )

    # ------------------------------------------------------------------------------ #
    # Resource cycles,
    # these wont work for experiments!
    # ------------------------------------------------------------------------------ #

    if input_type == "simulation":
        if not only_test_layout:
            # speed things up by not doing the analysis
            ah.find_module_level_adaptation(h5f)

        ax = fig.add_subplot(gs[1, 1])
        x_sets = []
        y_sets = []
        colors = []
        for mod_id in [0, 1, 2, 3]:
            try:
                y = h5f[f"ana.rates.module_level.mod_{mod_id}"]
                x = h5f[f"ana.adaptation.module_level.mod_{mod_id}"]
                dt = h5f[f"ana.rates.dt"]
                assert (
                    h5f[f"ana.adaptation.dt"] == dt
                ), "adaptation and rates need to share the same time step"
            except:
                continue
            # limit data range to whats needed
            x = x[0 : int(writer.tend / dt) + 2]
            y = y[0 : int(writer.tend / dt) + 2]
            x_sets.append(x)
            y_sets.append(y)
            colors.append(f"C{mod_id}")

        flr = FadingLineRenderer(
            x=x_sets,
            y=y_sets,
            colors=colors,
            dt=dt,
            ax=ax,
            tbeg=writer.tbeg,
            clip_on=False,
        )
        flr.decay_time = decay_time

        ax.set_xlim(0, 1)
        ax.xaxis.set_major_locator(matplotlib.ticker.MultipleLocator(1.0))
        ax.xaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(0.2))
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(150))
        ax.yaxis.set_minor_locator(matplotlib.ticker.MultipleLocator(50))
        ax.set_ylim(-15, 150)
        ax.yaxis.tick_right()
        ax.yaxis.set_ticks_position("both")
        sns.despine(ax=ax, left=True, right=False, top=True, trim=True, offset=1)
        # workaround for despine
        ax.yaxis.set_major_locator(matplotlib.ticker.MultipleLocator(100))

        ax.set_xlabel("Resources")
        ax.set_ylabel("")
        # ax.yaxis.set_visible(False)

        writer.renderers.append(flr)

    # ------------------------------------------------------------------------------ #
    # raster plot
    # ------------------------------------------------------------------------------ #

    ax = fig.add_subplot(gs[0, 3])

    ph.plot_raster(h5f=h5f, ax=ax)

    sns.despine(ax=ax, right=True, top=True, left=True, bottom=True)
    # ax.yaxis.set_visible(False)
    ax.xaxis.set_visible(False)
    ax.set_xlabel("")
    ax.set_ylabel("")
    # ax.set_ylabel("Raster")
    # ax.yaxis.labelpad = 10
    ax.tick_params(left=False, labelleft=False)

    if input_type == "experiment":
        # avoid cropping of raster markers, due to few neurons
        ax.set_ylim(-1, None)

    axis_to_data = ax.transAxes + ax.transData.inverted()
    ti_y_pos = -0.05
    ti_y_pos = axis_to_data.transform([1, ti_y_pos])[1]
    ti = ax.plot([0], [ti_y_pos], marker="^", markersize=3, color="white", clip_on=False)[
        0
    ]

    writer.renderers.append(
        MovingWindowRenderer(
            ax=ax,
            tbeg=writer.tbeg,
            tend=writer.tend,
            window_from=window_from,
            window_to=window_to,
            time_indicator=ti.set_xdata,
        )
    )

    # ------------------------------------------------------------------------------ #
    # Finalize and movie loop
    # ------------------------------------------------------------------------------ #

    fig.text(0.61, 0.9, "Raster", fontsize=8, ha="right")
    fig.text(0.61, 0.48, "Rates (Hz)", fontsize=8, ha="right")

    if title is not None:
        fig.text(0.19, 0.95, title, fontsize=8, ha="center", va="top")

    if show_time:
        writer.renderers.append(TextRenderer(fig.text(0.45, 0.8, "Time", fontsize=8)))

    fig.tight_layout()

    if only_test_layout:
        for r in writer.renderers:
            r.set_time(tbeg + (tend - tbeg) / 2)
    else:
        writer.render()


if __name__ == "__main__":
    main()