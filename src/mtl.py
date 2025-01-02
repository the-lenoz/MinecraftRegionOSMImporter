import sys
from pathlib import Path


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def get_texture_from_line(line: str) -> str | None:
    if line.startswith('map_') or \
            line.startswith('disp') or \
            line.startswith('decal') or \
            line.startswith('bump'):

        line_list = line.split(' ')
        texture_path = ''

        for i in range(1, len(line_list)):
            if not line_list[-i].startswith('-') and not is_number(line_list[-i]):
                texture_path = line_list[-i] + ' ' + texture_path

        if texture_path:
            return texture_path.strip()


def get_color_from_line(line: str) -> tuple | None:
    if line.startswith('Ka') or \
            line.startswith('Kd'):

        line_list = line.split(' ')

        value = tuple((float(line_list[-1]) for i in range(1, len(line_list)) if is_number(line_list[-i])))[::-1][:3]

        if len(value) == 3:
            return value


def get_material_from_file(config: dict, mtl_file_path: Path, material_name: str) -> str | None:
    with open(mtl_file_path) as mtl_file:
        material_data = mtl_file.read()

    material_name_index = material_data.find(material_name + '\t')
    if material_name_index == -1:
        material_name_index = material_data.find(material_name + '\n')
    if material_name_index == -1:
        material_name_index = material_data.find(material_name + ' ')
    if material_name_index == -1:
        return None

    material_data_crop = material_data[material_name_index:]

    material_end_index = material_data_crop.find('newmtl')

    found_material_data_lines = material_data_crop[:material_end_index].strip().split('\n')

    for line in found_material_data_lines:
        texture_path_string = get_texture_from_line(line)
        if texture_path_string:
            material_id = get_material_id_by_texture(config['material_texture_dictionary'], texture_path_string)
            if not material_id:
                print(f'Skipping unknown material: {material_name} with texture {texture_path_string}', file=sys.stderr)
                return
            return material_id

    for line in found_material_data_lines:
        color = get_color_from_line(line)
        if color:
            min_distance = None
            chosen_id = None
            for material_id, rgb in config['material_color_dictionary'].items():
                distance = (color[0] - rgb[0]) ** 2 + (color[1] - rgb[1]) ** 2 + (color[2] - rgb[2]) ** 2
                if min_distance is None or distance < min_distance:
                    min_distance = distance
                    chosen_id = material_id
            return chosen_id


def get_material_id_by_texture(texture_dictionary: dict, texture_path: str) -> str | None:
    for material_pattern, material_id in texture_dictionary.items():
        if material_pattern in texture_path:
            return material_id


def get_material_sort_key(material_dictionary: dict):
    def key(material) -> int:
        material = material_dictionary.get(material[0], None)
        if material:
            return material[1]
        else:
            return 0

    return key
