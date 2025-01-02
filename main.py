from typing import List, Dict

import sys
import os

from pathlib import Path
import tempfile

import argparse
import subprocess

from json import load

import numpy as np

import anvil

import requests

from datetime import datetime

from concurrent.futures import ProcessPoolExecutor

from mathematics import MapProjection
from voxelizer import voxelize_mesh, make_terrain
from mtl import get_material_from_file, get_material_sort_key

CONFIG_FILE = Path('config.json')


def read_config(path: Path):
    with open(path) as config_file:
        loaded_config = load(config_file)
    return loaded_config


def check_osm2world_stderr(stderr) -> bool:
    return True  # Add checking for elevation calculation fail


def download_map_data(config: dict, bbox: tuple, output_file_path: Path):
    url = config['url'].format(lat0=bbox[0][0], lon0=bbox[0][1], lat1=bbox[1][0], lon1=bbox[1][1])
    response = requests.get(url)
    with open(output_file_path, 'w') as osm_file:
        osm_file.write(response.text)


def run_osm2world(java_executable: Path, config: dict, output_file_path: Path, map_data_path: Path) -> None:
    command = [java_executable, '-jar', config['jar'],
               '--input', map_data_path,
               '-o', output_file_path,
               '--config', config['config-file']]

    completed_process = subprocess.run(command, capture_output=True, cwd=config['path'])
    if completed_process.returncode:
        print(completed_process.stderr.decode(), sys.stderr)
        raise Exception('Run OSM2World failed, trace is above.')

    if not check_osm2world_stderr(completed_process.stderr):
        print(completed_process.stderr.decode(), sys.stderr)
        raise Exception('OSM2World generated wrong elevation, trace is above.')


def run_splitter(java_executable: Path, config: dict, input_file_path: Path, output_directory_path: Path) -> Dict[
    str, Path]:
    command = [java_executable, '-jar', config['jar'], input_file_path, output_directory_path]

    completed_process = subprocess.run(command, capture_output=True, cwd=config['path'])

    if completed_process.returncode:
        print(completed_process.stderr.decode(), sys.stderr)
        raise Exception('Run splitter failed, trace is above.')

    output = completed_process.stdout.decode()
    output_lines_list = output.strip().split('\n')

    output_dictionary = {}
    for line in output_lines_list:
        line_separated = line.split(config['separator-signature'])
        output_dictionary[line_separated[0]] = Path(line_separated[1])

    return output_dictionary


def process_material(args):
    (material_name, material_mesh_path, material_dictionary, osm2world_output_file_path, config,
     region_min_bound, region_max_bound, region_offset, region_size_x, region_size_z, region_center_x, region_center_z,
     terrain_blocks) = args
    material = material_dictionary.get(material_name)
    if material:
        material_id = material[0]
    else:
        material_id = get_material_from_file(config['voxelizer'], Path(str(osm2world_output_file_path) + '.mtl'),
                                             material_name)

    if material_id:
        material_block = anvil.Block('minecraft', material_id)

        if material_mesh_path:
            voxel_list = voxelize_mesh(material_mesh_path, region_min_bound, region_max_bound, region_offset)
            voxels = [(voxel, material_block) for voxel in voxel_list]
            return voxels


def main(config, region_x, region_z, region_directory_path: Path):
    start_time = datetime.now()
    java_executable_path = Path(config['java'])

    center_lat = config['map']['center_lat']
    center_lon = config['map']['center_lon']

    region_size_x = config['map']['region_size_x']
    region_size_z = config['map']['region_size_z']

    download_width = config['map']['download_width']
    download_length = config['map']['download_length']

    material_dictionary = config['voxelizer']['material_dictionary']

    print(f'Initialized with center coordinates at: ({center_lat}, {center_lon})')

    projection = MapProjection(center_lat, center_lon)

    region_center_x = int((region_x + 0.5) * region_size_x)
    region_center_z = int((region_z + 0.5) * region_size_z)

    download_map_south_z = region_center_z + download_length / 2
    download_map_north_z = region_center_z - download_length / 2

    download_map_western_x = region_center_x - download_width / 2
    download_map_eastern_x = region_center_x + download_width / 2

    map_bbox = (projection.to_lat_lon(-download_map_south_z, download_map_western_x),
                projection.to_lat_lon(-download_map_north_z, download_map_eastern_x))

    print(f'Got bounding box of map to download: {map_bbox}')

    with tempfile.TemporaryDirectory() as temporary_directory_path_plain:
        temporary_directory_path = Path(temporary_directory_path_plain)
        print('Downoading osm data')

        osm_file_path = temporary_directory_path / 'map_data.osm'
        download_map_data(config['downloader'], map_bbox, osm_file_path)

        print('Download complete!')
        print('Running OSM2World')

        osm2world_output_file_path = temporary_directory_path / 'osm2world_output.obj'

        run_osm2world(java_executable_path, config['osm2world'], osm2world_output_file_path, osm_file_path)

        print('OSM2World finished!')
        print('Running material splitter')
        splitter_output_directory_path = temporary_directory_path / 'splitter_output'
        splitter_output_directory_path.mkdir()

        splited_files_dictionary = run_splitter(java_executable_path, config['splitter'],
                                                osm2world_output_file_path, splitter_output_directory_path)

        print('Material splitter finished!')

        region = anvil.EmptyRegion(region_x, region_z, config['voxelizer']['max_y'])

        region_min_bound = np.array([-region_size_x / 2, config['map']['min_height'], -region_size_z / 2])
        region_max_bound = np.array([region_size_x / 2 - 1,
                                     config['voxelizer']['max_y'] + config['map']['min_height'] - config['voxelizer'][
                                         'min_y'], region_size_z / 2 - 1])

        region_offset = np.array(
            [region_center_x, config['voxelizer']['min_y'] - config['map']['min_height'], region_center_z])

        print('Starting voxelization')

        terrain_blocks = [anvil.Block('minecraft', block_id) for block_id in config['voxelizer']['terrain_blocks']]

        splitted_materials = sorted(splited_files_dictionary.items(), key=get_material_sort_key(material_dictionary))

        terrain_material_objects = []
        terrain_material = material_dictionary.get(config['voxelizer']['terrain_material_name'])
        if terrain_material:
            terrain_material_id = terrain_material[0]

            terrain_material_block = anvil.Block('minecraft', terrain_material_id)

            i = 0
            while i < len(splitted_materials):
                if splitted_materials[i][0] == config['voxelizer']['terrain_material_name']:
                    terrain_material_objects.append(splitted_materials.pop(i))
                else:
                    i += 1

        with ProcessPoolExecutor() as executor:
            materials_voxels = executor.map(process_material, (
                (material_name, material_mesh_path, material_dictionary, osm2world_output_file_path, config,
                 region_min_bound, region_max_bound, region_offset, region_size_x, region_size_z, region_center_x,
                 region_center_z,
                 terrain_blocks) for material_name, material_mesh_path in splitted_materials))

        height_matrix = None
        terrain_matrix = None
        object_voxels_list = []
        terrain_voxels_list = []
        if terrain_material_objects:
            print('Generating terrain')
            height_matrix = [[None for x in range(region_size_x)] for z in range(region_size_z)]
            terrain_matrix = [[False for x in range(region_size_x)] for z in range(region_size_z)]

            for terrain_material_object in terrain_material_objects:
                terrain_voxels_list.extend(
                    voxelize_mesh(terrain_material_object[1], region_min_bound, region_max_bound, region_offset))

            for x, y, z in terrain_voxels_list:
                x, z = x % region_size_x, z % region_size_z
                if height_matrix and (height_matrix[z][x] is None or y > height_matrix[z][x]):
                    height_matrix[z][x] = y
                    terrain_matrix[z][x] = True

        for voxels in materials_voxels:
            if voxels:
                for (x, y, z), block in voxels:
                    object_voxels_list.append(((x, y, z), block))
                    x, z = x % region_size_x, z % region_size_z
                    if (height_matrix and terrain_matrix and
                        not terrain_matrix[z][x] and
                        (height_matrix[z][x] is None or y < height_matrix[z][x])) and block.id in config['voxelizer'][
                        'terrain_interpolator_markers']:
                        height_matrix[z][x] = y

        if terrain_material_object is not None:
            terrain_voxels_list = make_terrain(height_matrix, config['voxelizer']['min_y'],
                                               int(region_center_x - region_size_x / 2),
                                               int(region_center_z - region_size_z / 2),
                                               terrain_material_block, anvil.Block('minecraft', 'bedrock'),
                                               terrain_blocks)
            print('Terrain generation finished!')

        for (x, y, z), block in terrain_voxels_list + object_voxels_list:
            region.set_block(block, x, y, z)

        print('Voxelization finished!')
        print('Saving')

        region.save(str(region_directory_path / f'r.{region_x}.{region_z}.mca'))

        end_time = datetime.now()
        print(f'Done in {end_time - start_time}!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='MinecraftRegionOSMImporter',
        description='This utilite can get OSM data and write it to minecraft region files')

    parser.add_argument('--config', dest='config_file_path', default=None, help='Config file path')
    parser.add_argument('-x', type=int, required=True, help='Region X coordinate')
    parser.add_argument('-z', type=int, required=True, help='Region Z coordinate')
    parser.add_argument('-O', '--output', dest='output_directory_path', required=True, help='Output directory path')

    args = parser.parse_args()

    readed_config = read_config(Path(args.config_file_path if args.config_file_path else CONFIG_FILE))

    main(readed_config, args.x, args.z, Path(args.output_directory_path))
