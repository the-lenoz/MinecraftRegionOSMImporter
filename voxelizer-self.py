from typing import List

from pathlib import Path

import numpy as np

#import open3d as o3d
import trimesh

from random import choice
from math import sqrt

from concurrent.futures import ProcessPoolExecutor

from tqdm import tqdm

from triangle_cube_intersection import Point3, Triangle3, t_c_intersection


def voxelize_mesh(mesh_path: Path, min_bound: np.array, max_bound: np.array, offset: np.array, progress: bool = False) -> List[tuple]:
    #mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    mesh = trimesh.load(mesh_path)
    
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.to_mesh()
    
    #voxelized_mesh = o3d.geometry.VoxelGrid.create_from_triangle_mesh(mesh, voxel_size=1)

    voxels = []
    in_region_coordinates_translator = np.array([1,1,-1])
    '''
    half_corrector = 0 if float(voxelized_mesh.get_voxel_center_coordinate(voxelized_mesh.get_voxels()[0].grid_index)[0]) % 1 < 0.5 else 0.5
    for voxel in voxelized_mesh.get_voxels():
        voxel_coordinates = np.int32((voxelized_mesh.get_voxel_center_coordinate(voxel.grid_index) - half_corrector)
                                   * in_region_coordinates_translator)
                                   '''
    triangles = [[mesh.vertices[triangle[0]], mesh.vertices[triangle[1]], mesh.vertices[triangle[2]]] for triangle in mesh.faces]
    
    
    
    for voxel in voxelize(triangles, min_bound, max_bound, progress=progress):
        voxel_coordinates = np.array(voxel)
        voxel_coordinates[0], voxel_coordinates[2] = voxel_coordinates[2], voxel_coordinates[0]
        if np.all(voxel_coordinates >= min_bound) and np.all(voxel_coordinates <= max_bound):
            voxels.append(tuple(map(round, voxel_coordinates + offset)))
    
    return voxels


def voxelize(triangles: List, min_bound: np.array, max_bound: np.array, progress: bool = False) -> set:
    voxels = set()
    with ProcessPoolExecutor() as executor:
        for voxel_set in tqdm(executor.map(voxelize_triangle, ((triangle, min_bound, max_bound) for triangle in triangles)), total=len(triangles)) \
            if progress else executor.map(voxelize_triangle, ((triangle, min_bound, max_bound) for triangle in triangles)):
            voxels.update(voxel_set)
    return voxels

def voxelize_triangle(args):
    triangle, min_bound, max_bound = args
    voxels = set()
    bbox_min = np.floor(np.min(triangle, axis=0)).astype(np.int32)
    bbox_max = np.ceil(np.max(triangle, axis=0)).astype(np.int32)
    
    shape = bbox_max - bbox_min + 1
    
    if (np.all(bbox_max < min_bound) or np.all(bbox_min > max_bound)):
        return voxels
    
    with np.errstate(divide='ignore'):
        for x in range(shape[0]):
            for y in range(shape[1]):
                for z in range(shape[2]):
                    voxel = np.array([x, y, z]) + bbox_min
                    if np.all(voxel >= min_bound) and np.all(voxel <= max_bound):
                        v1, v2, v3 = map(lambda v: Point3(*(v - voxel)), triangle)
                        if t_c_intersection(Triangle3(v1, v2, v3)):
                            voxels.add(tuple(map(int, voxel)))
    return voxels


def make_terrain(voxel_list: List, region_size_x: int, region_size_z: int, min_y: int, region_min_x: int, region_min_z: int,
                 terrain_cover_block, terrain_bottom_block, terrain_blocks: List, offset: int = -8) -> List[tuple]:
    voxels = []
    height_matrix = [[None for x in range(region_size_x)] for z in range(region_size_z)]
    minimal_height = None
    
    for x, y, z in voxel_list:
        if height_matrix[z - region_min_z][x - region_min_x] is None or y < height_matrix[z - region_min_z][x - region_min_x]:
            height_matrix[z - region_min_z][x - region_min_x] = y
        if minimal_height is None or y < minimal_height:
            minimal_height = y
    
    for z in range(region_size_z):
        for x in range(region_size_x):
            voxels.append(((x + region_min_x, min_y, z + region_min_z), terrain_bottom_block))
            if height_matrix[z][x] is None:
                height_matrix[z][x] = minimal_height #max(get_interpolated(height_matrix, x, z) + offset, min_y + 1)
            voxels.append(((x,height_matrix[z][x],z), terrain_cover_block))
            for y in range(min_y + 1, height_matrix[z][x]):
                voxels.append(((x + region_min_x, y, z + region_min_z), choice(terrain_blocks)))
    return voxels   


def get_interpolated(matrix: List[List[int]], x: int, z: int, found_weight: float = 2):
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
                
        if divider == 0:
            raise ValueError('Empty matrix')
        return round(summ / divider)
