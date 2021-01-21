import pwspy.dataTypes as pwsdt
import typing as t_
import matplotlib.pyplot as plt
from matplotlib import widgets
import numpy as np

# TODO replace `matplotlib.widgets` with the improved mpl_qt_viz stuff

def selectPointROI(cube: pwsdt.ICBase, side: int = 3, displayIndex: t_.Optional[int] = None):
    """
    Allow the user to select a single point on an image of the acquisition.

    Args:
        side (int): The length (in pixels) of the sides of the square that is used for selection.
        displayIndex (Optional[int]): The z-slice of the 3d array which should be displayed

    Returns:
        np.ndarray: An array of the 4 XY vertices of the square.
    """
    from mpl_qt_viz.roiSelection import PointCreator
    verts = [None]
    if displayIndex is None:
        displayIndex = cube.data.shape[2] // 2
    fig, ax = plt.subplots()
    ax.imshow(cube.data[:, :, displayIndex])
    fig.suptitle("Close to accept ROI")

    def select(Verts, handles):
        verts[0] = Verts

    sel = PointCreator(ax, onselect=select, sideLength=side)
    sel.set_active(True)
    fig.show()
    while plt.fignum_exists(fig.number):
        fig.canvas.flush_events()
    return np.array(verts[0])


def selectLassoROI(cube: pwsdt.ICBase, displayIndex: t_.Optional[int] = None, clim: t_.Sequence = None) -> np.ndarray:
    """
    Allow the user to draw a `freehand` ROI on an image of the acquisition.

    Args:
        displayIndex: Display a particular z-slice of the array for mask drawing. If `None` then the mean along Z is displayed.

    Returns:
        An array of vertices of the polygon drawn.
    """
    Verts = [None]
    if displayIndex is None:
        displayIndex = cube.data.shape[2]//2
    fig, ax = plt.subplots()
    data = cube.data[:, :, displayIndex]
    ax.imshow(data, clim=[np.percentile(data, 1), np.percentile(data, 99)])
    fig.suptitle("Close to accept ROI")

    def onSelect(verts):
        Verts[0] = verts

    l = widgets.LassoSelector(ax, onSelect, lineprops={'color': 'r'})
    fig.show()
    while plt.fignum_exists(fig.number):
        fig.canvas.flush_events()
    return np.array(Verts[0])

def selectRectangleROI(cube: pwsdt.ICBase, displayIndex: t_.Optional[int] = None) -> np.ndarray:
    """
    Allow the user to draw a rectangular ROI on an image of the acquisition.

    Args:
        displayIndex (int): is used to display a particular z-slice for mask drawing. If None then the mean along Z is displayed. Returns an array of vertices of the rectangle.

    Returns:
        np.ndarray: An array of the 4 XY vertices of the rectangle.
    """
    import warnings
    warnings.warn("This method has been moved to the `pwspy_gui.utility` module and will be removed in the future.",
                  category=DeprecationWarning)

    verts = [None]

    if displayIndex is None:
       displayIndex = cube.data.shape[2]//2
    fig, ax = plt.subplots()
    ax.imshow(cube.data[:, :, displayIndex])
    fig.suptitle("Close to accept ROI")

    def rectSelect(mins, maxes):
        verts[0] = ((mins.ydata, mins.xdata), (maxes.ydata, mins.xdata), (maxes.ydata, maxes.xdata), (mins.ydata, maxes.xdata))

    r = widgets.RectangleSelector(ax, rectSelect)
    fig.show()
    while plt.fignum_exists(fig.number):
        fig.canvas.flush_events()
    return np.array(verts[0])
