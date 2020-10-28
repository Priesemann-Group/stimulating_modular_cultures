# ------------------------------------------------------------------------------ #
# @Author:        F. Paul Spitzner
# @Email:         paul.spitzner@ds.mpg.de
# @Created:       2020-09-28 10:36:48
# @Last Modified: 2020-10-28 11:27:53
# ------------------------------------------------------------------------------ #
# My implementation of the logISI historgram burst detection algorithm
# by Pasuqale et al.
#
# Adapted from R-code https://github.com/ellesec/burstanalysis
# Original Algorithm: DOI 10.1007/s10827-009-0175-1
# Comparison by Ellese et al: DOI 10.1152/jn.00093.2016
#
# Only detects the bursts within each Channel / ROI / Unit. Thus, if we want to
# include short network bursts (less than 3 spikes per neuron),
# we need sth else.
#
# ToDo: Network-burst detection.
# ------------------------------------------------------------------------------ #

import sys
import os
import logging
import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess
from scipy.signal import find_peaks
from tqdm import tqdm


sys.path.append(os.path.abspath(os.path.dirname(__file__) + "/../ana/"))
import utility as ut

log = logging.getLogger(__name__)
# log.setLevel("DEBUG")

# value to return if no bursts found.
no_bursts = dict()
for key in ["beg", "end", "med", "IBI", "blen", "durn", "mean_isis"]:
    no_bursts[key] = np.array([]).astype(int)


def burst_detection_pasquale(spike_train, cutoff=0.1):
    """
        burst detection for single neuron/channel/roi spike trains.

        this implements the main method described in DOI 10.1007/s10827-009-0175-1
        but only on a single spiketrain, not on a network level

        Parameters
        ----------
        spike_train: 1d array
            time stamps of the neurons' spikes, in seconds

        cutoff: float
            threshold for the isi, in seconds.
            Burst will be required to have a lower isi than this cutoff.

        Returns
        -------
        bursts: dict
            with the following keys, each with a 1d array of len = number bursts:
            * beg: the index in the train of the first spike in the burst
            * end: the index of the last spike of the burst
            * med: the time of the median spike within the burst
            * IBI: time from last spike of the prev. burst to first spike of this burst
            * blen: number of spikes counting into the burst
            * durn: duration of the burst, first spike to last spike
            * mean_isis: the mean inter spike interval within the burst

        isi_low: float
            the threshold where we separate between inter- and intra-burst intervals.

        hist: array
            the histogram with all inter-spike-interval counts

        edges: array
            the bin edges of the isi histogram (from np.histogram)
    """

    if len(spike_train) > 3:
        # Calculates threshold as isi_low
        isi_low, hist, hist_smooth, edges = logisi_break_calc(spike_train, cutoff)
        log.debug(f"isi_low {isi_low}")
        if isi_low is None or isi_low >= 1:
            # If no value for isi_low found, or isi_low above 1 second, find bursts using threshold equal to cutoff (default 100ms)
            result = logisi_find_burst(
                spike_train, min_ibi=0, min_durn=0, min_spikes=3, isi_low=cutoff
            )

        elif isi_low < 0:
            result = no_bursts

        elif isi_low > cutoff and isi_low < 1:
            # If isi_low >cutoff, find bursts using threshold equal to cutoff (default 100ms)
            bursts = logisi_find_burst(
                spike_train, min_ibi=isi_low, min_durn=0, min_spikes=3, isi_low=cutoff
            )
            if bursts is not None:
                # If bursts have been found, add burst related spikes using threshold of isi_low
                brs = logisi_find_burst(
                    spike_train, min_ibi=0, min_durn=0, min_spikes=3, isi_low=isi_low
                )
                result = add_brs(bursts, brs, spike_train)
            else:
                result = bursts

        else:
            # If isi_low<cutoff, find bursts using a threshold equal to isi_low
            result = logisi_find_burst(
                spike_train, min_ibi=0, min_durn=0, min_spikes=3, isi_low=isi_low
            )

    else:
        return [no_bursts] + [None] * 3

    return result, isi_low, hist, edges


# Function to find cutoff threshold.
def find_thresh(h, h_edges, ISITh=100.0, void_th=0.7, peak_kwargs=None):
    log.debug("find_thresh")
    if peak_kwargs is None:
        peak_kwargs = {"width": 1}
    log.debug(f"kwargs: {peak_kwargs}")
    # this is an ugly workaround because find_peaks is not detecting maxima at edges
    h = np.insert(h, 0, -np.inf)
    h_edges = np.insert(h_edges, 0, -np.inf)
    peak_idx, peak_props = find_peaks(h, height=0, **peak_kwargs)
    # peak_idx = peakutils.peak.indexes(h, thres=0.0, min_dist=3)
    num_peaks = len(peak_idx)
    peak_pos = h_edges[peak_idx]
    peak_heights = peak_props["peak_heights"]
    # peak_heights = h[peak_idx]
    # find peak position of the intra-burst-isi, if below the specified threshold
    if (peak_pos < ISITh).any():
        last_idx = np.where(peak_pos < ISITh)[0][-1]
        intra_idx = np.argmax(peak_heights[0:last_idx]) if last_idx > 0 else 0
        intra_height = peak_heights[intra_idx]
    else:
        return -1000.0

    y1 = intra_height
    x1 = peak_idx[intra_idx]
    log.debug(f"peak_idx {peak_idx}")
    log.debug(f"peak_heights {peak_heights}")

    log.debug(f"x1: {intra_idx}")
    log.debug(f"y1: {intra_height}")
    log.debug(f"last_idx: {last_idx}")
    num_peaks_after_burst = num_peaks - intra_idx

    if num_peaks_after_burst == 0:
        return None
    else:
        x_2s = peak_idx[intra_idx + 1 :]
        y_2s = peak_heights[intra_idx + 1 :]
        # x_2s = np.delete(x_2s, [3,6])
        # y_2s = np.delete(y_2s, [3,6])

        log.debug(f"h {h}")
        log.debug(f"x1 {x1}")
        log.debug(f"x_2s {x_2s}")
        log.debug(f"num_peaks {num_peaks}")

        if len(x_2s) == 0:
            return None

        f = lambda x: np.amin(h[x1:x])
        ymins = np.vectorize(f)(x_2s)

        f = lambda x: np.argmin(h[x1:x])
        # log.debug(h[x1 : x_2s[0]])
        # log.debug(h[x1 : x_2s[-1]])
        xmins = np.vectorize(f)(x_2s) + x1

        void_pars = 1 - (ymins / np.sqrt(y1 * y_2s))

        log.debug(f"ymins: {ymins}")
        log.debug(f"xmins: {xmins}")
        log.debug(f"void_pars: {void_pars}")

    try:
        void_idx = np.where(void_pars >= void_th)[0][0]
        log.debug(f"void idx: {void_idx}")
    except:
        void_idx = None

    if void_idx is None:
        return None
    else:
        log.debug(f"ISImax: {h_edges[xmins[void_idx]]}")
        return h_edges[xmins[void_idx]]


debug_h = None
debug_s = None
debug_e = None
debug_spikes = None

# Calculates cutoff for burst detection
def logisi_break_calc(st, cutoff, void_th=0.7, peak_kwargs=None):

    global debug_h
    global debug_s
    global debug_e
    global debug_isi
    global debug_spikes

    isi = np.diff(st) * 1000.0
    debug_spikes = st
    isi = isi[isi >= 1]
    max_isi = np.ceil(np.log10(np.max(isi)))
    br = np.logspace(0, max_isi, int(10 * max_isi))
    hist, edges = np.histogram(isi, bins=br, density=True)
    hist_smooth = lowess(
        endog=hist,
        exog=np.arange(len(hist)),
        frac=0.05,
        is_sorted=True,
        return_sorted=False,
    )
    debug_h = hist
    debug_s = hist_smooth
    debug_e = edges / 1000.0

    # log.debug(hist_smooth)
    thr = find_thresh(
        h=hist_smooth,
        h_edges=edges,
        ISITh=cutoff * 1000.0,
        void_th=void_th,
        peak_kwargs=peak_kwargs,
    )
    log.debug(f"thr: {thr}")
    if not thr is None:
        thr = thr / 1000.0

    return thr, hist, hist_smooth, edges / 1000.0


###Function to add burst related spikes to edges of bursts
def add_brs(bursts, brs, spikes):
    def is_between(x, a, b):
        return (x >= a) & (x <= b)

    num_bursts = len(bursts["beg"])
    num_brs = len(brs["beg"])
    burst_adj = {
        "beg": np.zeros(num_bursts).astype(int),
        "end": np.zeros(num_bursts).astype(int),
    }

    for i in range(num_bursts):
        for j in range(num_brs):
            if is_between(bursts["beg"][i], brs["beg"][j], brs["end"][j]) or is_between(
                bursts["end"][i], brs["beg"][j], brs["end"][j]
            ):
                burst_adj["beg"][i] = np.fmin(bursts["beg"][i], brs["beg"][j])
                burst_adj["end"][i] = np.fmax(bursts["end"][i], brs["end"][j])
                break
            else:
                burst_adj["beg"][i] = bursts["beg"][i]
                burst_adj["end"][i] = bursts["end"][i]

            if brs["end"][j] > bursts["end"][i]:
                break

    diff_begs = np.diff(burst_adj["beg"])
    diff_ends = np.diff(burst_adj["end"])

    rejects = np.array([])
    rejects = np.concatenate((rejects, np.where(diff_begs == 0)[0]))
    rejects = np.concatenate((rejects, np.where(diff_ends == 0)[0] + 1))
    rejects = np.sort(np.unique(rejects))

    if len(rejects) > 0:
        for key in burst_adj.keys():
            np.delete(burst_adj[key], rejects)

    burst_adj["blen"] = burst_adj["end"] - burst_adj["beg"] + 1
    burst_adj["durn"] = spikes[burst_adj["end"]] - spikes[burst_adj["beg"]]
    burst_adj["mean_isis"] = burst_adj["durn"] / (burst_adj["blen"] - 1)

    ibis = spikes[burst_adj["beg"][1:]] - spikes[burst_adj["end"][:-1]]
    ibis = np.insert(ibis, 0, np.nan)
    burst_adj["IBI"] = ibis

    # get the median time of the burst
    f = lambda b: np.median(spikes[burst_adj["beg"][b] : burst_adj["end"][b]])
    burst_adj["med"] = (
        np.vectorize(f)(np.arange(len(burst_adj["beg"])))
        if len(burst_adj["beg"]) > 0
        else np.array([])
    )

    return burst_adj


##Function for finding bursts, taken from sjemea
def logisi_find_burst(spikes, min_ibi, min_durn, min_spikes, isi_low, neuron_ids=None):
    """
        Find bursts, taken from sjemea

        Parameters
        ----------
        spikes: array
            containing the spike times

        min_ibi : float
            minimal interval to separate two bursts, otherwise will be merged

        min_durn, min_spikes: floats
            minimal burst-duration and number of spikes required to count as burst

        isi_low: float
            threshold for isi, isis below this value are taken to be in a burst.

        neuron_ids : np.array
            used when detecting network bursts. this array should contain the id of
            the neuron that caused the spike/burst contained in the passed 'spike' array.
            default None.
            If not None, the min_spikes requirement checks for unique contributions.

        Returns
        -------
        bursts: dict with various keys, containing arrays with the burst details.
        if 'neuron_ids' is provided in addition to the default keys, also 'unique'
        is present. this contains the number of unique neurons that were involved
        in a network burst.

    """

    ## For one spike train, find the burst using log isi method.
    ## e.g.
    ## find.bursts(s$spikes[[5]])
    ## init.
    ##

    nspikes = len(spikes)

    ## Create a temp array for the storage of the bursts.  Assume that
    ## it will not be longer than Nspikes/2 since we need at least two
    ## spikes to be in a burst.

    max_bursts = np.floor(nspikes / 2)

    bursts = []

    # current burst number
    burst = 0

    ## Phase 1 -- burst detection. Each interspike interval of the data
    ## is compared with the threshold THRE. If the interval is greater
    ## than the threshold value, it can not be part of a burst; if the
    ## interval is smaller or equal to the threhold, the interval may be
    ## part of a burst.

    ## last_end is the time of the last spike in the previous burst.
    ## This is used to calculate the IBI.
    ## For the first burst, this is no previous IBI
    last_end = np.nan

    eps = 1e-10
    n = 1
    in_burst = False

    log.debug("logisi_find_burst:")
    log.debug(f"nspikes {nspikes}")
    log.debug(f"isi_low {isi_low}")

    while n < nspikes - 1:
        next_isi = spikes[n] - spikes[n - 1]
        if in_burst:
            if next_isi - isi_low > eps:
                ## end of burst
                end = n - 1
                in_burst = False

                ibi = spikes[beg] - last_end
                last_end = spikes[end]
                res = np.array([beg, end, ibi])
                burst = burst + 1

                assert burst <= max_bursts
                bursts.append(res)

        else:
            ## not yet in burst.
            if next_isi - isi_low <= eps:
                ## Found the start of a new burst.
                beg = n - 1
                in_burst = True

        n = n + 1

    ## At the end of the burst, check if we were in a burst when the
    ## train finished.
    if in_burst:
        end = nspikes - 1
        ibi = spikes[beg] - last_end
        res = np.array([beg, end, ibi])
        burst = burst + 1
        assert burst <= max_bursts
        bursts.append(res)

    ## Check if any bursts were found.
    if burst > 0:
        # convert bursts into a dictionary of 1d arrays
        bursts = np.array(bursts)
        bursts = {
            "beg": bursts[:, 0].astype(int),
            "end": bursts[:, 1].astype(int),
            "IBI": bursts[:, 2],
        }

    else:
        ## no bursts were found, so return an empty structure.
        return no_bursts

    log.debug("End of phase 1")
    log.debug(f"num bursts before rejections: {len(bursts['beg'])}")
    # log.debug(bursts)

    ## Phase 2 -- merging of bursts.    Here we see if any pair of bursts
    ## have an IBI less than min_ibi; if so, we then merge the bursts.
    ## We specifically need to check when say three bursts are merged
    ## into one.

    ibis = bursts["IBI"]
    rejects = np.array([])

    if (ibis < min_ibi).any():
        ## Merge bursts efficiently.    Work backwards through the list, and
        ## then delete the merged lines afterwards.    This works when we
        ## have say 3+ consecutive bursts that merge into one.

        # remove these later
        merge_bursts = np.where(ibis < min_ibi)[0]
        log.debug(f"ibis < min_ibi: {len(merge_bursts)}")
        rejects = merge_bursts

        for burst in reversed(merge_bursts):
            bursts["end"][burst - 1] = bursts["end"][burst]
            # bursts["end"][burst] = np.nan  # not needed, but helpful.

    log.debug("End of phase 2\n")
    # log.debug(bursts)

    ## Phase 3 -- remove small bursts: less than min duration (MIN_DURN), or
    ## having too few spikes (less than MIN_SPIKES).
    ## In this phase we have the possibility of deleting all spikes.

    ## BLEN = number of spikes in a burst.
    ## DURN = duration of burst.
    bursts["blen"] = bursts["end"] - bursts["beg"] + 1
    # log.debug(bursts["beg"])
    # log.debug(bursts["end"])
    bursts["durn"] = spikes[bursts["end"]] - spikes[bursts["beg"]]
    bursts["mean_isis"] = bursts["durn"] / (bursts["blen"] - 1)

    rejects = np.concatenate((rejects, np.where(bursts["durn"] < min_durn)[0]))
    if neuron_ids is None:
        rejects = np.concatenate((rejects, np.where(bursts["blen"] < min_spikes)[0]))
    else:
        unique = lambda b: len(
            np.unique(neuron_ids[bursts["beg"][b] : bursts["end"][b]])
        )
        bursts["unique"] = (
            np.vectorize(unique)(np.arange(len(bursts["beg"])))
            if len(bursts["beg"]) > 0
            else np.array([])
        )
        rejects = np.concatenate((rejects, np.where(bursts["unique"] < min_spikes)[0]))

    rejects = np.sort(np.unique(rejects))

    if len(rejects) > 0:
        for key in bursts.keys():
            bursts[key] = np.delete(bursts[key], rejects)

    log.debug(f"num bursts after rejections: {len(bursts['beg'])}")

    if len(bursts["beg"]) == 0:
        pass
        ## All the bursts were removed during phase 3.
        # bursts = no_bursts
    else:
        ## Recompute IBI (only needed if phase 3 deleted some cells).
        if len(bursts["beg"]) > 1:
            ibis = spikes[bursts["beg"][1:]] - spikes[bursts["end"][:-1]]
            ibis = np.insert(ibis, 0, np.nan)
        else:
            ibis = np.array([np.nan])

        bursts["IBI"] = ibis
        assert len(bursts["IBI"]) == len(bursts["beg"])

    # get the median time of the burst
    f = lambda b: np.median(spikes[bursts["beg"][b] : bursts["end"][b]])
    bursts["med"] = (
        np.vectorize(f)(np.arange(len(bursts["beg"])))
        if len(bursts["beg"]) > 0
        else np.array([])
    )

    ## End -- return burst structure.
    log.debug("logisi_find_burst done")
    return bursts


# ------------------------------------------------------------------------------ #
# network burst detection
# ------------------------------------------------------------------------------ #


def network_burst_detection(spiketimes, network_fraction=0.8, sort_by="beg"):
    """
        Detection of network bursts using the logisi method by pasquale et al.
        The log-histogram trick is applied two times, once on the per-neuron-
        level and then on the network level.

        Parameters
        ----------
        spiketimes : 2d np array
            nan-padded spiketimes. first dim neurons, second dim spiketimes

        network_fraction : float
            the fraction of unique neurons that need to be bursting (on the
            single-neuron level) in order to detect a network burst

        sort_by : str
            "beg", "med", or "end"; default is "beg"
            what criterion to sort neuron-level bursts by for the network
            burst detection. only impacts the sequence of contributing
            neurons in bursts, not the bursts themselves.


        Returns
        -------
        network_bursts: dict
            containing the network bursts

        details: dict
            containing details such as the neuron-level bursts, neuron id
            corresponding to a burst etc.
    """
    assert sort_by in ["beg", "med", "end"]
    num_n = spiketimes.shape[0]

    # flat list of all bursts that occured on the single-neuron level
    # beginning, median, end times
    med_times = []
    beg_times = []
    end_times = []
    # which neuron did burst
    neuron_ids = []


    for n in tqdm(range(num_n), leave=None):
        train = spiketimes[n]
        train = train[np.isfinite(train)]
        train = train[np.nonzero(train)]
        bursts, _, _, _ = burst_detection_pasquale(train)
        neuron_ids += [n] * len(bursts["med"])
        med_times += bursts["med"].tolist()
        # in the burst strucutre, beg and end are indices, convert to times.
        beg_times += train[bursts["beg"]].tolist()
        end_times += train[bursts["end"]].tolist()

    neuron_ids = np.array(neuron_ids)
    med_times = np.array(med_times)
    beg_times = np.array(beg_times)
    end_times = np.array(end_times)

    details = dict()
    details["neuron_ids"] = np.array([])
    details["med_times"] = np.array([])
    details["beg_times"] = np.array([])
    details["end_times"] = np.array([])

    if len(med_times) == 0:
        return no_bursts, details

    # sort neuron-level bursts according to burst time, depending on user choice
    if sort_by == "beg":
        burst_times = beg_times
    elif sort_by == "end":
        burst_times = end_times
    elif sort_by == "med":
        burst_times = med_times

    idx = np.argsort(burst_times)
    burst_times = burst_times[idx]
    details["neuron_ids"] = neuron_ids[idx]
    details["med_times"] = med_times[idx]
    details["beg_times"] = beg_times[idx]
    details["end_times"] = end_times[idx]

    try:
        thr, hist, hist_smooth, edges = logisi_break_calc(
            burst_times, cutoff=0.2, void_th=0, peak_kwargs={}
        )
    except Exception as e:
        log.debug(f"logisi_break_calc: {e}")
        return no_bursts, details

    # log.setLevel("DEBUG")
    try:
        nb = logisi_find_burst(
            spikes=burst_times,
            min_ibi=0.25,
            min_durn=0,
            min_spikes=int(network_fraction * num_n),
            isi_low=thr,
            neuron_ids=details["neuron_ids"],
        )
    except Exception as e:
        log.info(f"find_burst: {e}")

    return nb, details
