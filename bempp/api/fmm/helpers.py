import numpy as _np
import numba as _numba

M_INV_4PI = 1.0 / (4 * _np.pi)


@_numba.jit(
    nopython=True, parallel=False, error_model="numpy", fastmath=True, boundscheck=False
)
def laplace_kernel(target_points, source_points, kernel_parameters, dtype, result_type):
    """Evaluate the Laplace kernel."""

    ntargets = target_points.shape[1]
    nsources = source_points.shape[1]
    m_inv_4pi = dtype.type(M_INV_4PI)

    interactions = _np.empty(4 * ntargets * nsources, dtype=result_type)
    diff = _np.zeros((3, nsources), dtype=dtype)
    for target_point_index in range(ntargets):
        dist = _np.zeros(nsources, dtype=dtype)
        for i in range(3):
            for j in range(nsources):
                diff[i, j] = target_points[i, target_point_index] - source_points[i, j]
                dist[j] += diff[i, j] * diff[i, j]
        for j in range(nsources):
            dist[j] = _np.sqrt(dist[j])
        for j in range(nsources):
            interactions[target_point_index * 4 * nsources + 4 * j] = (
                m_inv_4pi / dist[j]
            )
        for i in range(3):
            for j in range(nsources):
                interactions[target_point_index * 4 * nsources + 4 * j + 1 + i] = (
                    -diff[i, j] * m_inv_4pi / (dist[j] * dist[j] * dist[j])
                )
        # Now fix zero distance case
        for j in range(nsources):
            if dist[j] == 0:
                for i in range(4):
                    interactions[target_point_index * 4 * nsources + 4 * j + i] = 0

    return interactions


@_numba.jit(
    nopython=True, parallel=False, error_model="numpy", fastmath=True, boundscheck=False
)
def modified_helmholtz_kernel(
    target_points, source_points, kernel_parameters, dtype, result_type
):
    """Evaluate the modified Helmholtz kernel."""

    ntargets = target_points.shape[1]
    nsources = source_points.shape[1]
    m_inv_4pi = dtype.type(M_INV_4PI)

    interactions = _np.empty(4 * ntargets * nsources, dtype=result_type)
    diff = _np.zeros((3, nsources), dtype=dtype)
    for target_point_index in range(ntargets):
        dist = _np.zeros(nsources, dtype=dtype)
        for i in range(3):
            for j in range(nsources):
                diff[i, j] = target_points[i, target_point_index] - source_points[i, j]
                dist[j] += diff[i, j] * diff[i, j]
        for j in range(nsources):
            dist[j] = _np.sqrt(dist[j])
        for j in range(nsources):
            interactions[target_point_index * 4 * nsources + 4 * j] = (
                m_inv_4pi * _np.exp(-kernel_parameters[0] * dist[j]) / dist[j]
            )
        for i in range(3):
            for j in range(nsources):
                interactions[target_point_index * 4 * nsources + 4 * j + 1 + i] = (
                    (-kernel_parameters[0] * dist[j] - 1)
                    * diff[i, j]
                    * _np.exp(-kernel_parameters[0] * dist[j])
                    * m_inv_4pi
                    / (dist[j] * dist[j] * dist[j])
                )
        # Now fix zero distance case
        for j in range(nsources):
            if dist[j] == 0:
                for i in range(4):
                    interactions[target_point_index * 4 * nsources + 4 * j + i] = 0

    return interactions


@_numba.jit(
    nopython=True, parallel=False, error_model="numpy", fastmath=True, boundscheck=False
)
def helmholtz_kernel(
    target_points, source_points, kernel_parameters, dtype, result_type
):
    """Evaluate the Laplace kernel."""

    ntargets = target_points.shape[1]
    nsources = source_points.shape[1]
    m_inv_4pi = dtype.type(M_INV_4PI)

    wavenumber = kernel_parameters[0]

    tmp_real = _np.empty(nsources, dtype=dtype)
    tmp_imag = _np.empty(nsources, dtype=dtype)
    interactions_real = _np.empty(4 * ntargets * nsources, dtype=dtype)
    interactions_imag = _np.empty(4 * ntargets * nsources, dtype=dtype)
    diff = _np.zeros((3, nsources), dtype=dtype)
    for target_point_index in range(ntargets):
        dist = _np.zeros(nsources, dtype=dtype)
        for i in range(3):
            for j in range(nsources):
                diff[i, j] = target_points[i, target_point_index] - source_points[i, j]
                dist[j] += diff[i, j] * diff[i, j]
        for j in range(nsources):
            dist[j] = _np.sqrt(dist[j])
        for j in range(nsources):
            tmp_real[j] = m_inv_4pi * _np.cos(wavenumber * dist[j]) / dist[j]
            tmp_imag[j] = m_inv_4pi * _np.sin(wavenumber * dist[j]) / dist[j]
        for j in range(nsources):
            interactions_real[target_point_index * 4 * nsources + 4 * j] = tmp_real[j]
            interactions_imag[target_point_index * 4 * nsources + 4 * j] = tmp_imag[j]
        for i in range(3):
            for j in range(nsources):
                interactions_real[target_point_index * 4 * nsources + 4 * j + 1 + i] = (
                    (-tmp_real[j] - wavenumber * dist[j] * tmp_imag[j])
                    / (dist[j] * dist[j])
                    * diff[i, j]
                )
                interactions_imag[target_point_index * 4 * nsources + 4 * j + 1 + i] = (
                    (-tmp_imag[j] + wavenumber * dist[j] * tmp_real[j])
                    / (dist[j] * dist[j])
                    * diff[i, j]
                )

        # Now fix zero distance case
        for j in range(nsources):
            if dist[j] == 0:
                for i in range(4):
                    interactions_real[target_point_index * 4 * nsources + 4 * j + i] = 0
                    interactions_imag[target_point_index * 4 * nsources + 4 * j + i] = 0

    return interactions_real + 1j * interactions_imag


def get_local_interaction_matrix(
    grid, local_points, kernel_function, kernel_parameters, precision, is_complex
):

    from bempp.api.utils.helpers import get_type
    from scipy.sparse import csr_matrix

    npoints = local_points.shape[1]

    dtype = _np.dtype(get_type(precision).real)
    if is_complex:
        result_type = _np.dtype(get_type(precision).complex)
    else:
        result_type = dtype

    data, indices, indexptr = get_local_interaction_matrix_impl(
        grid.data(precision),
        local_points.astype(dtype),
        kernel_function,
        _np.array(kernel_parameters, dtype=dtype),
        dtype,
        result_type,
    )

    rows = 4 * npoints * grid.number_of_elements
    cols = npoints * grid.number_of_elements

    return csr_matrix((data, indices, indexptr), shape=(rows, cols))


@_numba.jit(
    nopython=True, parallel=True, error_model="numpy", fastmath=True, boundscheck=False
)
def get_local_interaction_matrix_impl(
    grid_data, local_points, kernel_function, kernel_parameters, dtype, result_type
):
    """Get the local interaction matrix on the grid."""
    nelements = grid_data.elements.shape[1]
    npoints = local_points.shape[1]
    neighbor_indices = grid_data.element_neighbor_indices
    neighbor_indexptr = grid_data.element_neighbor_indexptr

    data = _np.zeros(4 * npoints * npoints * len(neighbor_indices), dtype=result_type)
    indexptr = _np.zeros(4 * npoints * nelements + 1, dtype=_np.uint32)
    indices = _np.zeros(4 * npoints * npoints * len(neighbor_indices), dtype=_np.uint32)
    indexptr[-1] = 4 * npoints * npoints * len(neighbor_indices)

    global_points = _np.zeros((nelements, 3, npoints), dtype=dtype)

    for element_index in range(nelements):
        global_points[element_index, :, :] = grid_data.local2global(
            element_index, local_points
        )

    for target_element in _numba.prange(nelements):
        target_points = global_points[target_element]
        nneighbors = (
            neighbor_indexptr[1 + target_element] - neighbor_indexptr[target_element]
        )
        source_elements = _np.sort(
            neighbor_indices[
                neighbor_indexptr[target_element] : neighbor_indexptr[
                    1 + target_element
                ]
            ]
        )

        local_source_points = _np.empty((3, npoints * nneighbors), dtype=dtype)
        for source_element_index in range(nneighbors):
            source_element = source_elements[source_element_index]
            local_source_points[
                :, npoints * source_element_index : npoints * (1 + source_element_index)
            ] = global_points[source_element, :, :]
        local_target_points = global_points[target_element, :, :]
        interactions = kernel_function(
            local_target_points,
            local_source_points,
            kernel_parameters,
            dtype,
            result_type,
        )

        local_count = 4 * npoints * npoints * neighbor_indexptr[target_element]
        for target_point_index in range(npoints):
            for i in range(4):
                indexptr[
                    4 * npoints * target_element + 4 * target_point_index + i
                ] = local_count
                for source_element_index in range(nneighbors):
                    source_element = source_elements[source_element_index]
                    for source_point_index in range(npoints):
                        data[local_count] = interactions[
                            4 * target_point_index * nneighbors * npoints
                            + 4 * source_element_index * npoints
                            + 4 * source_point_index
                            + i
                        ]
                        indices[local_count] = (
                            npoints * source_element + source_point_index
                        )
                        local_count += 1

    return data, indices, indexptr


def map_space_to_points(space, local_points, weights, return_transpose=False):
    """Return mapper from grid coeffs to point evaluations."""
    import bempp.api
    from scipy.sparse import coo_matrix
    from scipy.sparse.linalg import aslinearoperator

    grid = space.grid
    number_of_local_points = local_points.shape[1]
    nshape_funs = space.number_of_shape_functions
    number_of_vertices = number_of_local_points * grid.number_of_elements

    data, global_indices, vertex_indices = map_space_to_points_impl(
        grid.data("double"),
        space.localised_space.local2global,
        space.localised_space.local_multipliers,
        space.localised_space.normal_multipliers,
        space.support_elements,
        space.numba_evaluate,
        space.shapeset.evaluate,
        local_points,
        weights,
        space.number_of_shape_functions,
    )

    if return_transpose:
        transform = coo_matrix(
            (data, (global_indices, vertex_indices)),
            shape=(space.localised_space.global_dof_count, number_of_vertices),
        )

        return aslinearoperator(space.map_to_localised_space.T) @ aslinearoperator(
            transform
        )
    else:
        transform = coo_matrix(
            (data, (vertex_indices, global_indices)),
            shape=(number_of_vertices, space.localised_space.global_dof_count),
        )
        return aslinearoperator(transform) @ aslinearoperator(
            space.map_to_localised_space
        )


@_numba.njit
def map_space_to_points_impl(
    grid_data,
    local2global,
    local_multipliers,
    normal_multipliers,
    support_elements,
    numba_evaluate,
    shape_fun,
    local_points,
    weights,
    number_of_shape_functions,
):
    """Numba accelerated computational parts for point map."""

    number_of_local_points = local_points.shape[1]
    number_of_support_elements = len(support_elements)

    nlocal = number_of_local_points * number_of_shape_functions

    data = _np.empty(nlocal * number_of_support_elements, dtype=_np.float64)
    global_indices = _np.empty(nlocal * number_of_support_elements, dtype=_np.int64)
    vertex_indices = _np.empty(nlocal * number_of_support_elements, dtype=_np.int64)

    for elem in support_elements:
        basis_values = (
            numba_evaluate(
                elem,
                shape_fun,
                local_points,
                grid_data,
                local_multipliers,
                normal_multipliers,
            )[0, :, :]
            * weights
            * grid_data.integration_elements[elem]
        )
        data[elem * nlocal : (1 + elem) * nlocal] = basis_values.ravel()
        for index in range(number_of_shape_functions):
            vertex_indices[
                elem * nlocal
                + index * number_of_local_points : elem * nlocal
                + (1 + index) * number_of_local_points
            ] = _np.arange(
                elem * number_of_local_points, (1 + elem) * number_of_local_points
            )
        global_indices[elem * nlocal : (1 + elem) * nlocal] = _np.repeat(
            local2global[elem, :], number_of_local_points
        )

    return (data, global_indices, vertex_indices)


@_numba.njit
def grid_to_points(grid_data, local_points):
    """
    Map a grid to an array of points.

    Returns a (N, 3) point array that stores the global vertices
    associated with the local points in each triangle.
    Points are stored in consecutive order for each element 
    in the support_elements list. Hence, the returned array is of the form
    [ v_1^1, v_2^1, ..., v_M^1, v_1^2, v_2^2, ...], where
    v_i^j is the ith point in the jth element in
    the support_elements list.

    Parameters
    ----------
    grid_data : GridData
        A Bempp GridData object.
    local_points : np.ndarray
        (2, M) array of local coordinates.
    """
    number_of_elements = grid_data.elements.shape[1]
    number_of_points = local_points.shape[1]

    points = _np.empty((number_of_points * number_of_elements, 3), dtype=_np.float64)

    for elem in range(number_of_elements):
        points[number_of_points * elem : number_of_points * (1 + elem), :] = (
            _np.expand_dims(grid_data.vertices[:, grid_data.elements[0, elem]], 1)
            + grid_data.jacobians[elem].dot(local_points)
        ).T
    return points