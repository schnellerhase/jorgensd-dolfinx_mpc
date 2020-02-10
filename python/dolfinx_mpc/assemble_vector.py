# Copyright (C) 2020 Jørgen S. DOkken
#
# This file is part of DOLFIN (https://www.fenicsproject.org)
#
# SPDX-License-Identifier:    LGPL-3.0-or-later
from .numba_setup import ffi, PETSc
import numba
import numpy


@numba.njit
def assemble_vector_numba(b, kernel, mesh, x, dofmap, mpc, ghost_info, bcs):
    """Assemble provided FFC/UFC kernel over a mesh into the array b"""
    (bcs, values) = bcs
    (slaves, masters, coefficients, offsets,
     slave_cells, cell_to_slave, cell_to_slave_offset) = mpc
    local_range, global_indices, ghosts = ghost_info

    connections, pos = mesh
    orientation = numpy.array([0], dtype=numpy.int32)
    geometry = numpy.zeros((3, 2))
    coeffs = numpy.zeros(1, dtype=PETSc.ScalarType)
    constants = numpy.zeros(1, dtype=PETSc.ScalarType)
    constants = numpy.ones(1, dtype=PETSc.ScalarType)
    b_local = numpy.zeros(3, dtype=PETSc.ScalarType)
    index = 0
    for i, cell in enumerate(pos[:-1]):
        num_vertices = pos[i + 1] - pos[i]
        c = connections[cell:cell + num_vertices]
        for j in range(3):
            for k in range(2):
                geometry[j, k] = x[c[j], k]
        b_local.fill(0.0)
        kernel(ffi.from_buffer(b_local), ffi.from_buffer(coeffs),
               ffi.from_buffer(constants),
               ffi.from_buffer(geometry), ffi.from_buffer(orientation),
               ffi.from_buffer(orientation))
        # if len(bcs) > 1:
        #     for k in range(3):
        #         if bcs[dofmap[i * 3 + k]]:
        #             b_local[k] = 0
        if i in slave_cells:
            b_local_copy = b_local.copy()
            # Determine which slaves are in this cell,
            # and which global index they have in 1D arrays
            cell_slaves = cell_to_slave[cell_to_slave_offset[index]:
                                        cell_to_slave_offset[index+1]]
            index += 1
            glob = dofmap[3 * i:3 * i + 3]
            # Find which slaves belongs to each cell
            global_slaves = []
            for gi, slave in enumerate(slaves):
                if slaves[gi] in cell_slaves:
                    global_slaves.append(gi)
            # Loop over the slaves
            for s_0 in range(len(global_slaves)):
                slave_index = global_slaves[s_0]
                cell_masters = masters[offsets[slave_index]:
                                       offsets[slave_index+1]]
                cell_coeffs = coefficients[offsets[slave_index]:
                                           offsets[slave_index+1]]
                # Variable for local position of slave dof
                # slave_local = 0
                # for k in range(len(glob)):
                #     if global_indices[glob[k]] == slaves[slave_index]:
                #         slave_local = k

                # Loop through each master dof to take individual contributions
                for m_0 in range(len(cell_masters)):
                    if slaves[slave_index] == cell_masters[m_0]:
                        print("No slaves (since slave is same as master dof)")
                        continue

                    # Find local dof and add contribution to another place
                    for k in range(len(glob)):
                        if global_indices[glob[k]] == slaves[slave_index]:
                            c0 = cell_coeffs[m_0]
                            # Map to local index
                            local_index = -1
                            if cell_masters[m_0] < local_range[1] and cell_masters[m_0] > local_range[0]:
                                local_index = cell_masters[m_0]-local_range[0]
                            else:
                                # Inverse mapping from ghost info
                                for q,ghost in enumerate(ghosts):
                                    if cell_masters[m_0] == ghost:
                                        local_index = q + local_range[1]-local_range[0]
                                        # break
                                        pass
                            b[local_index] += c0*b_local_copy[k]
                            b_local[k] = 0
        for j in range(3):
            b[dofmap[i * 3 + j]] += b_local[j]


    # for k in range(len(bcs)):
    #     if bcs[k]:

    #         b[k] = values[k]
