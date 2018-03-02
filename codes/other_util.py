"""
Utility functions for demonstration or illustration. Mostly copied from individual python scripts
"""

import numpy as np
import cv2
import librosa
import scipy.ndimage as ndimage
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
% matplotlib inline

def getSpec(sig, rate, power=2, **kwargs):
    """
    Get spectrogram from signal split
    
    Options:
    - power : integer, 1 or 2
      Specify the power of spectrogram. Defaults to intensity
      For power = 1, return amplitude spectrogram
    """
    
    ## melspetrogram
    magspec = librosa.feature.melspectrogram(y=sig,sr=rate,power=power,**kwargs)
    
    return magspec


def getMultiSpec(path, seconds=3., overlap=2.5, minlen=3., **kwargs):
    """
    Split signal into chunks with overlap of certain seconds and tunable minimum length
    
    Options:
    - seconds : np.float
      Length of output chunk (segment) of audio. Defaults to 3 seconds
    
    - overlap : np.float
      Length of overlapping window of segmentation. Defaults to 2.5 seconds
      
    - minlen : np.float
      Minimal length of output spectrogram in seconds. Defaults to 3 seconds.
    """
    #--
    ## open audio file
    sig, rate = librosa.load(path,sr=None) # natural sample rate
    
    ## adjust to different sample rates
    if rate != 44100:
        sig  = librosa.resample(sig, rate, 44100)

    #--
    ## split signal with overlap
    sig_splits = []
    for i in xrange(0, len(sig), int((seconds - overlap) * rate)):
        split = sig[i:i + int(seconds*rate)]
        if len(split) >= minlen * rate:
            sig_splits.append(split)

    ## if signal too short for segmentation, append it anyway
    if len(sig_splits) == 0:
        sig_splits.append(sig)
    
    #--
    ## calculate spectrogram for each split
    for sig in sig_splits:
        magspec = getSpec(sig, rate, **kwargs)

        yield magspec


def hasBird(spec, threshold=30):
    """
    Decide if given spectrum shows bird sounds or noise only
    
    Options:
    - threshold : float
      Threshold value for separating real signal / noise. Defaults to 30.
      Changeable via command-line option (see above)
    """
    ## working copy
    img = spec.copy().astype(np.float32)

    ### STEP 0: get rid of highest/lowest freq bins
    img = img[20:100,:] # total of 128 bins
    
    ### STEP 1: Median blur
    img = cv2.medianBlur(img,5)

    ### STEP 2: Median threshold
    col_median = np.median(img, axis=0, keepdims=True)
    row_median = np.median(img, axis=1, keepdims=True)

    img[img < row_median * 3] = 0.
    img[img < col_median * 4] = 0.
    img[img > 0] = 1.

    #### STEP 3: Morph Closing
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((5,5), np.float32))
    ### STEP 4: Count columns and rows with signal
    #-- (Note: We only use rows with signal as threshold -- time axis for fixed freqs)
    
    ##### row has signal?
    row_max = np.max(img, axis=1)
    row_max = ndimage.morphology.binary_dilation(row_max, iterations=2).astype(row_max.dtype)
    rthresh = row_max.sum()
    
    ### STEP 5: Apply threshold
    bird = True
    if rthresh < threshold:
        bird = False
    
    return bird, img