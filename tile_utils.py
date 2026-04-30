import numpy as np
from math import pi, atan, sinh, pow
import openeo

# In-memory storage for active layer cubes and their states
active_layers = {}

def tile_to_bbox(x, y, z):
    """Converts XYZ tile coordinates to a WGS84 Bounding Box."""
    def n(x, y, z):
        lon = x / pow(2, z) * 360 - 180
        lat = atan(sinh(pi * (1 - 2 * y / pow(2, z)))) * 180 / pi
        return lon, lat
    lon_min, lat_max = n(x, y, z)
    lon_max, lat_min = n(x + 1, y + 1, z)
    return {
        "west": lon_min, 
        "south": lat_min, 
        "east": lon_max, 
        "north": lat_max,
        "crs": "EPSG:4326"
    }

def get_8bit_tile(layer_id, x, y, z):
    if layer_id not in active_layers:
        return None
    
    entry = active_layers[layer_id]
    cube = entry['cube']
    vis = entry['vis']
    
    # 1. Calculate the bounding box for this specific tile
    tile_bbox = tile_to_bbox(x, y, z)

    try:
        # 2. Slice the cube to the tile extent
        tile_cube = cube.filter_bbox(**tile_bbox)
        
        # 3. Apply Visualization Parameters
        if vis['mode'] == '1band':
            # Handle Single Band (Grayscale)
            # If it's a calculated layer, the band might be named 'index'
            band_name = vis['bands'] if isinstance(vis['bands'], str) else vis['bands'][0]
            processed = tile_cube.band(band_name)
        else:
            # Handle RGB (3-band)
            processed = tile_cube.filter_bands(vis['bands'])
        
        # 4. Scale values to 8-bit (0-255) for PNG rendering
        # Range comes from the styling parameters (default 0-3000 for S2)
        vmin, vmax = vis['range']
        img_8bit = processed.linear_scale_range(vmin, vmax, 0, 255)
        
        # 5. Download the rendered PNG bytes
        return cube.connection.download(img_8bit.save_result(format="PNG"))

    except Exception as e:
        # Catch "head of empty array" or "NoSuchElementException"
        # This happens when a tile is requested where no data exists (outside AOI)
        if "empty array" in str(e) or "NoSuchElementException" in str(e):
            print(f"DEBUG: Tile {z}/{x}/{y} is empty (outside AOI/No data). Skipping.")
        else:
            print(f"ERROR: Tile rendering failed for {z}/{x}/{y}: {str(e)}")
        return None

def get_layer_metadata(layer_id):
    if layer_id not in active_layers:
        return None
        
    entry = active_layers[layer_id]
    
    # Simulated metadata and histogram for the Properties interface
    # In a production environment, you would use cube.summarize() or samples
    return {
        "name": entry['name'],
        "bands": entry['all_bands'],
        "crs": "EPSG:3857",
        "spatial_res": "10m",
        "histogram": [int(x) for x in np.random.normal(128, 40, 256).clip(0, 255)]
    }
