"""Editable feature INIs live outside immutable packages and deployment bytes."""
import os
from .storage import contained

ENVIRONMENT = {
    'custom-keybinds': 'MOONLAB_KEYBINDS_CONFIG',
    'gambling': 'MOONLAB_GAMBLING_CONFIG',
    'item-stacking': 'MOONLAB_STACKING_CONFIG',
    'idle-vehicle-storage': 'MOONLAB_IDLE_VEHICLE_STORAGE_CONFIG',
    'rover-horns': 'MOONLAB_HORN_SETTINGS',
    'mars-planet': 'MOONLAB_MARS_PLANET_SETTINGS',
    'multi-belt-balancer': 'MOONLAB_BALANCER_CONFIG',
    'precise-build-snapping': 'MOONLAB_SNAPPING_CONFIG',
    'conveyor-upgrade-wrench': 'MOONLAB_CONVEYOR_TIERS_CONFIG',
    'area-blueprints': 'MOONLAB_BLUEPRINTS_CONFIG',
    'building-drone': 'MOONLAB_BUILDING_DRONE_CONFIG',
    'joonas-backpack': 'MOONLAB_JOONAS_BACKPACK_CONFIG',
    'player-catapult': 'MOONLAB_PLAYER_CATAPULT_CONFIG',
}


def environment(root, order, platform):
    result = {}
    for name in order:
        if name not in ENVIRONMENT: continue
        path = str(contained(root, 'settings/' + name + '.ini'))
        result[ENVIRONMENT[name]] = path if platform == 'win32' else 'Z:' + path.replace('/', '\\')
    return result


def seed(root, order, library):
    """First preparation supplies defaults; later prepares preserve user edits."""
    for name in order:
        if name not in ENVIRONMENT: continue
        manifest, folder = library[name]
        if 'settings.ini' not in manifest['files']: continue
        target = contained(root, 'settings/' + name + '.ini')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open('xb') as output:
                output.write(contained(folder, 'settings.ini').read_bytes())
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            pass
