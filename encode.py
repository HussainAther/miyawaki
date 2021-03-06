from matplotlib.colors import LinearSegmentedColormap

import matplotlib as mpl
mpl.use('TkAgg')

import numpy as np
import pylab as pl
import nibabel
import os
import sys
import time

bluegreen = LinearSegmentedColormap('bluegreen', {
    'red': ((0., 0., 0.),
            (1., 0., 0.)),
    'green': ((0., 0., 0.),
              (1., 1., 1.)),
    'blue': ((0., 0.2, 0.2),
             (0.5, 0.5, 0.5),
             (1., 0., 0.))
    })

### Load Miyawaki dataset #####################################################
import datasets
dataset = datasets.get_miyawaki()

# Keep only random runs
X_random = dataset.func[12:]
y_random = dataset.label[12:]
y_shape = (10, 10)

### Preprocess data ###########################################################
import masking, preprocess

sys.stderr.write("Preprocessing data...")
t0 = time.time()

# Load and mask fMRI data
X_train = []
for x_random in X_random:
    # Mask data
    x_img = nibabel.load(x_random)
    x = masking.apply_mask(x_img, dataset.mask)
    x = preprocess.clean(x)
    X_train.append(x[2:])

# Load target data and reshape it in 2D
y_train = []
for y in y_random:
    y_train.append(np.reshape(np.loadtxt(y, dtype=np.int, delimiter=','),
        (-1,) + y_shape, order='F')[:-2].astype(float))

X_train = np.vstack(X_train)
y_train = np.vstack(y_train)

# Flatten the stimuli
y_train = np.reshape(y_train, (-1, y_shape[0] * y_shape[1]))

sys.stderr.write(" Done (%.2fs)\n" % (time.time() - t0))
n_pixels = y_train.shape[1]
n_features = X_train.shape[1]

### Encoding using Lasso regression and Ridge regression

from sklearn.linear_model import Ridge
from sklearn.linear_model import Lasso
from sklearn.cross_validation import KFold

print("Ridge regression")
estimator_ridge = Ridge(alpha=100, normalize=True, max_iter=1e5)

print("Lasso regression")
estimator_lasso = Lasso(alpha=100, normalize=True, max_iter=1e5)

cv = KFold(len(y_train), 10)
predictions_lasso = [
        estimator_lasso.fit(y_train.reshape(-1, 100)[train], X_train[train]
            ).predict(y_train.reshape(-1, 100)[test]) for train, test in cv]
predictions_ridge = [
        estimator_ridge.fit(y_train.reshape(-1, 100)[train], X_train[train]
            ).predict(y_train.reshape(-1, 100)[test]) for train, test in cv]

print("Scoring")
scores_ridge = [1. - (((X_train[test] - pred) ** 2).sum(axis=0) /
           ((X_train[test] - X_train[test].mean(axis=0)) ** 2).sum(axis=0))
for pred, (train, test) in zip(predictions_ridge, cv)]

scores_lasso = [1. - (((X_train[test] - pred) ** 2).sum(axis=0) /
           ((X_train[test] - X_train[test].mean(axis=0)) ** 2).sum(axis=0))
for pred, (train, test) in zip(predictions_lasso, cv)]

### Show scores

# Create a mask with chosen voxels to contour them
contour = np.zeros(nibabel.load(dataset.mask).shape, dtype=bool)
for x, y in [(31, 9), (31, 10), (30, 10), (32, 10)]:
    contour[x, y, 10] = 1


from matplotlib.lines import Line2D


def plot_lines(mask, linewidth=3, color='b'):
    for i, j in np.ndindex(mask.shape):
        if i + 1 < mask.shape[0] and mask[i, j] != mask[i + 1, j]:
            pl.gca().add_line(Line2D([j - .5, j + .5], [i + .5, i + .5],
                color=color, linewidth=linewidth))
        if j + 1 < mask.shape[1] and mask[i, j] != mask[i, j + 1]:
            pl.gca().add_line(Line2D([j + .5, j + .5], [i - .5, i + .5],
                color=color, linewidth=linewidth))

sbrain_ridge = masking.unmask(np.array(scores_ridge).mean(0), dataset.mask)

bg = nibabel.load(os.path.join('bg.nii.gz'))

pl.figure(figsize=(8, 8))
ax1 = pl.axes([0., 0., 1., 1.])
pl.imshow(bg.get_data()[:, :, 10].T, interpolation="nearest", cmap='gray',
          origin='lower')
pl.imshow(np.ma.masked_less(sbrain_ridge[:, :, 10].T, 1e-6),
          interpolation="nearest", cmap='hot', origin="lower")
plot_lines(contour[:, :, 10].T)
pl.axis('off')
ax2 = pl.axes([.08, .5, .05, .47])
cb = pl.colorbar(cax=ax2, ax=ax1)
cb.ax.yaxis.set_ticks_position('left')
cb.ax.yaxis.set_tick_params(labelcolor='white')
cb.ax.yaxis.set_tick_params(labelsize=20)
cb.set_ticks(np.arange(0., .8, .2))
pl.savefig(os.path.join('output', 'encoding_scores_ridge.pdf'))
pl.savefig(os.path.join('output', 'encoding_scores_ridge.png'))
pl.savefig(os.path.join('output', 'encoding_scores_ridge.eps'))
pl.clf()

sbrain_lasso = masking.unmask(np.array(scores_lasso).mean(0), dataset.mask)

pl.figure(figsize=(8, 8))
ax1 = pl.axes([0., 0., 1., 1.])
pl.imshow(bg.get_data()[:, :, 10].T, interpolation="nearest", cmap='gray',
          origin='lower')
pl.imshow(np.ma.masked_less(sbrain_lasso[:, :, 10].T, 1e-6),
          interpolation="nearest", cmap='hot', origin="lower")
plot_lines(contour[:, :, 10].T)
pl.axis('off')
ax2 = pl.axes([.08, .5, .05, .47])
cb = pl.colorbar(cax=ax2, ax=ax1)
cb.ax.yaxis.set_ticks_position('left')
cb.ax.yaxis.set_tick_params(labelcolor='white')
cb.ax.yaxis.set_tick_params(labelsize=20)
cb.set_ticks(np.arange(0., .8, .2))
pl.savefig(os.path.join('output', 'encoding_scores_lasso.pdf'))
pl.savefig(os.path.join('output', 'encoding_scores_lasso.png'))
pl.savefig(os.path.join('output', 'encoding_scores_lasso.eps'))
pl.clf()

### Compute receptive fields

from sklearn.linear_model import LassoLarsCV

lasso = LassoLarsCV(max_iter=10,)

p = (4, 2)
# Mask for chosen pixel
pixmask = np.zeros((10, 10), dtype=bool)
pixmask[p] = 1

for index in [1700, 1800, 1900, 2000]:
    rf = lasso.fit(y_train, X_train[:, index]).coef_.reshape(10, 10)
    pl.figure(figsize=(8, 8))
    # Black background
    pl.imshow(np.zeros_like(rf), vmin=0., vmax=1., cmap='gray')
    pl.imshow(np.ma.masked_equal(rf, 0.), vmin=0., vmax=0.75,
            interpolation="nearest", cmap=bluegreen)
    plot_lines(pixmask, linewidth=6, color='r')
    pl.axis('off')
    pl.subplots_adjust(left=0., right=1., bottom=0., top=1.)
    pl.savefig(os.path.join('output', 'encoding_%d.pdf' % index))
    pl.savefig(os.path.join('output', 'encoding_%d.eps' % index))
    pl.clf()


### Plot the colorbar #########################################################


fig = pl.figure(figsize=(2.4, .4))
norm = mpl.colors.Normalize(vmin=0., vmax=.75)
cb = mpl.colorbar.ColorbarBase(pl.gca(), cmap=bluegreen, norm=norm,
                               orientation='horizontal')
#cb.ax.yaxis.set_ticks_position('left')
cb.set_ticks([0., 0.38, 0.75])
fig.subplots_adjust(bottom=0.5, top=1., left=0.08, right=.92)
pl.savefig(os.path.join('output', 'encoding_rf_colorbar.pdf'))
pl.savefig(os.path.join('output', 'encoding_rf_colorbar.png'))
pl.savefig(os.path.join('output', 'encoding_rf_colorbar.eps'))
