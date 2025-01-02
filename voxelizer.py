from typing import List

from pathlib import Path

import numpy as np

import open3d as o3d

from random import choice
from math import sqrt

def voxelize_mesh(mesh_path: Path, min_bound: np.array, max_bound: np.array, offset: np.array) -> List[tuple]:
    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    
    voxelized_mesh = o3d.geometry.VoxelGrid.create_from_triangle_mesh(mesh, voxel_size=1)

    voxels = []
    in_region_coordinates_translator = np.array([1,1,1])
    half_corrector = 0 if float(voxelized_mesh.get_voxel_center_coordinate(voxelized_mesh.get_voxels()[0].grid_index)[0]) % 1 < 0.5 else 0.5
    for voxel in voxelized_mesh.get_voxels():
        voxel_coordinates = np.int32((voxelized_mesh.get_voxel_center_coordinate(voxel.grid_index) - half_corrector)
                                   * in_region_coordinates_translator)
        #voxel_coordinates[0], voxel_coordinates[2] = voxel_coordinates[2], voxel_coordinates[0]
        if np.all(voxel_coordinates >= min_bound) and np.all(voxel_coordinates <= max_bound):
            voxels.append(tuple(map(round, voxel_coordinates + offset)))
    
    return voxels

def make_terrain(height_matrix, min_y: int, region_min_x: int, region_min_z: int,
                 terrain_cover_block, terrain_bottom_block, terrain_blocks: List) -> List[tuple]:
    voxels = []
    
    for z in range(len(height_matrix)):
        for x in range(len(height_matrix[z])):
            voxels.append(((x + region_min_x, min_y, z + region_min_z), terrain_bottom_block))
            if height_matrix[z][x] is None:
                height_matrix[z][x] = max(get_interpolated(height_matrix, x, z), min_y + 1)
            voxels.append(((x + region_min_x, height_matrix[z][x], z + region_min_z), terrain_cover_block))
            for y in range(min_y + 1, height_matrix[z][x]):
                voxels.append(((x + region_min_x, y, z + region_min_z), choice(terrain_blocks)))
    return voxels   


def get_interpolated(matrix: List[List[int]], x: int, z: int, found_weight: float = 3):
    length = len(matrix)
    width = len(matrix[0])
    
    divider = 0
    summ = 0
    used = []
    
    for radius in range(1, int(max(length / 2, width / 2))):
        z_offset = -radius
        for x_offset in range(-radius, radius + 1):
            current_x = min(max(x + x_offset, 0), width - 1)
            current_z = min(max(z + z_offset, 0), length - 1)
            if matrix[current_z][current_x] is not None and (current_x, current_z) not in used:
                summ += matrix[current_z][current_x] / radius
                divider += 1 / radius
                used.append((current_x, current_z))
        
        for z_offset in range(-radius, radius + 1):
            x_offset = -radius
            current_x = min(max(x + x_offset, 0), width - 1)
            current_z = min(max(z + z_offset, 0), length - 1)
            if matrix[current_z][current_x] is not None and (current_x, current_z) not in used:
                summ += matrix[current_z][current_x] / radius
                divider += 1 / radius
                used.append((current_x, current_z))
                
            x_offset = radius
            current_x = min(max(x + x_offset, 0), width - 1)
            current_z = min(max(z + z_offset, 0), length - 1)
            if matrix[current_z][current_x] is not None and (current_x, current_z) not in used:
                summ += matrix[current_z][current_x] / radius
                divider += 1 / radius
                used.append((current_x, current_z))

        z_offset = radius
        for x_offset in range(-radius, radius + 1):
            current_x = min(max(x + x_offset, 0), width - 1)
            current_z = min(max(z + z_offset, 0), length - 1)
            if matrix[current_z][current_x] is not None and (current_x, current_z) not in used:
                summ += matrix[current_z][current_x] / radius
                divider += 1 / radius
                used.append((current_x, current_z))
        
        if divider >= found_weight:
            break
        
    if divider == 0:
        raise ValueError('Empty matrix')
    return round(summ / divider)
