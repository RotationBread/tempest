

import numpy as np
import os
from urllib.request import urlretrieve

import matplotlib
from matplotlib.colors import LinearSegmentedColormap
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.axes as maxes
import matplotlib.patheffects as PathEffects
from matplotlib.path import Path
from matplotlib.textpath import TextToPath
from matplotlib.font_manager import FontProperties
matplotlib.rcParams['font.sans-serif'] = 'Liberation Sans'
matplotlib.rcParams['font.family'] = "sans-serif"
from cartopy import cartopy, crs as ccrs, feature as cfeature

import xarray as xr
import pandas as pd
import json
import geoviews as gv
import geoviews.feature as gf
from geoviews import opts, tile_sources as gvts
from bokeh.models import Title

from datetime import datetime, timedelta, timezone

import warnings
warnings.filterwarnings("ignore")