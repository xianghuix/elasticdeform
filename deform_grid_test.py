import numpy as np
import scipy.ndimage
import unittest

import _deform_grid

# Python implementation
def deform_grid_py(X, displacement, order=3, crop=None):
    # compute number of control points in each dimension
    points = [displacement[0].shape[d] for d in range(X.ndim)]

    # creates the grid of coordinates of the points of the image (an ndim array per dimension)
    coordinates = np.meshgrid(*[np.arange(X.shape[d]) for d in range(X.ndim)], indexing='ij')
    # creates the grid of coordinates of the points of the image in the "deformation grid" frame of reference
    xi = np.meshgrid(*[np.linspace(0, points[d] - 1, X.shape[d]) for d in range(X.ndim)], indexing='ij')

    if crop is not None:
        coordinates = [c[crop] for c in coordinates]
        xi = [x[crop] for x in xi]

    # add the displacement to the coordinates
    for i in range(X.ndim):
        yd = scipy.ndimage.map_coordinates(displacement[i], xi, order=3)
        # adding the displacement
        coordinates[i] = np.add(coordinates[i], yd)

    return scipy.ndimage.map_coordinates(X, coordinates, order=order)

# C implementation wrapper
def deform_grid_c(X_in, displacement, order=3, crop=None):
    if isinstance(X_in, list):
        X = X_in
        shape = X_in[0].shape
        ndim = X_in[0].ndim
    else:
        X = [X_in]
        shape = X_in.shape
        ndim = X_in.ndim

    if crop is not None:
        output_shape = [shape[d] for d in range(ndim)]
        output_offset = [0 for d in range(ndim)]
        for d in range(ndim):
            if isinstance(crop[d], slice):
                assert crop[d].step is None
                start = (crop[d].start or 0)
                stop = (crop[d].stop or shape[d])
                assert start >= 0
                assert start < stop and stop <= shape[d]
                output_shape[d] = stop - start
                if start > 0:
                    output_offset[d] = start
            else:
                raise Exception("Crop must be a slice.")
        if any(o > 0 for o in output_offset):
            output_offset = np.array(output_offset)
        else:
            output_offset = None
    else:
        output_shape = shape
        output_offset = None

    if order > 1:
        X_sf = [scipy.ndimage.spline_filter(x, order=order) for x in X]
    else:
        X_sf = X
    displacement_sf = displacement
    for d in range(1, displacement.ndim):
        displacement_sf = scipy.ndimage.spline_filter1d(displacement_sf, axis=d, order=3)

    mode = 4  # NI_EXTEND_CONSTANT
    cval = 0.0

    outputs = [np.zeros(output_shape, dtype=x.dtype) for x in X]
    _deform_grid.deform_grid(X_sf, displacement_sf, output_offset, outputs, order, mode, cval)

    if isinstance(X_in, list):
        return outputs
    else:
        return outputs[0]


class TestDeformGrid(unittest.TestCase):
    def test_basic_2d(self):
        for points in ((3, 3), (3, 5), (1, 5)):
            for shape in ((100, 100), (100, 75)):
                for order in (1, 2, 3, 4):
                    self.run_comparison(shape, points, order=order)

    def test_basic_3d(self):
        for points in ((3, 3, 3), (3, 5, 7), (1, 3, 5)):
            for shape in ((50, 50, 50), (100, 50, 25)):
                for order in (1, 2, 3, 4):
                    self.run_comparison(shape, points, order=order)

    def test_crop_2d(self):
        points = (3, 3)
        shape = (100, 100)
        for crop in ((slice(0, 50), slice(0, 50)),
                     (slice(20, 60), slice(20, 60)),
                     (slice(50, 100), slice(50, 100))):
            for order in (1, 2, 3, 4):
                self.run_comparison(shape, points, crop=crop, order=order)

    def test_crop_3d(self):
        points = (3, 3, 5)
        shape = (25, 25, 25)
        order = 3
        for crop in ((slice(15, 25), slice(None), slice(None)),):
            self.run_comparison(shape, points, crop=crop, order=order)

    def test_multi_2d(self):
        points = (3, 3)
        shape = (100, 75)
        sigma = 25
        for order in (1, 2, 3, 4):
            for crop in (None, (slice(15, 25), slice(15, 50))):
                # generate random displacement vector
                displacement = np.random.randn(len(shape), *points) * sigma
                # generate random data
                X = np.random.rand(*shape)
                # generate more random data
                Y = np.random.rand(*shape)

                # test and compare
                res_X_ref = deform_grid_py(X, displacement, order=order, crop=crop)
                res_Y_ref = deform_grid_py(Y, displacement, order=order, crop=crop)
                [res_X_test, res_Y_test] = deform_grid_c([X, Y], displacement, order=order, crop=crop)

                np.testing.assert_array_almost_equal(res_X_ref, res_X_test)
                np.testing.assert_array_almost_equal(res_Y_ref, res_Y_test)

    def test_multi_3d(self):
        points = (3, 3, 3)
        shape = (25, 25, 30)
        sigma = 25
        for order in (1, 2, 3, 4):
            for crop in (None, (slice(15, 20), slice(15, 25), slice(2, 10))):
                # generate random displacement vector
                displacement = np.random.randn(len(shape), *points) * sigma
                # generate random data
                X = np.random.rand(*shape)
                # generate more random data
                Y = np.random.rand(*shape)

                # test and compare
                res_X_ref = deform_grid_py(X, displacement, order=order, crop=crop)
                res_Y_ref = deform_grid_py(Y, displacement, order=order, crop=crop)
                [res_X_test, res_Y_test] = deform_grid_c([X, Y], displacement, order=order, crop=crop)

                np.testing.assert_array_almost_equal(res_X_ref, res_X_test)
                np.testing.assert_array_almost_equal(res_Y_ref, res_Y_test)

    def run_comparison(self, shape, points, order=3, sigma=25, crop=None):
        # generate random displacement vector
        displacement = np.random.randn(len(shape), *points) * sigma
        # generate random data
        X = np.random.rand(*shape)

        # test and compare
        res_ref = deform_grid_py(X, displacement, order=order, crop=crop)
        res_test = deform_grid_c(X, displacement, order=order, crop=crop)

        np.testing.assert_array_almost_equal(res_ref, res_test)


if __name__ == '__main__':
    unittest.main()

