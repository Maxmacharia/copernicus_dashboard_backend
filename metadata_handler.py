import openeo
import os
import base64
import re
import traceback
import numpy as np
import xarray as xr
import io
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    conn = openeo.connect("https://openeo.dataspace.copernicus.eu")
    conn.authenticate_oidc_client_credentials(
        os.getenv("CLIENT_ID"),
        os.getenv("CLIENT_SECRET")
    )
    return conn


def apply_styling(data):
    print("\n--- [BACKEND] GEE-Style Visualization Scaling ---")
    try:
        params = data.get('style_params', {})
        is_calc = data.get('type') == 'calc'
        expression = data.get('expression')
        ramp = params.get('ramp', 'gray')

        conn = get_connection()

        # STEP 1: Determine and load required bands
        if is_calc and expression:
            load_bands = list(set(re.findall(r'"([^"]*)"', expression)))
        else:
            load_bands = [params['band']] if params['mode'] == '1-band' else [params['r'], params['g'], params['b']]

        cube = conn.load_collection(
            collection_id=data['collection'],
            spatial_extent=data['aoi'],
            temporal_extent=data['dates'],
            bands=load_bands
        )
        
        # Reduce temporal dimension
        processed = cube.reduce_dimension(dimension="t", reducer="median")

        # STEP 2: Isolate the continuous layer
        if is_calc and expression:
            clean_expr = expression.replace('"', '')
            bands_dict = {band: processed.band(band) for band in load_bands}
            final_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)
        else:
            final_cube = processed.band(params['band']) if params['mode'] == '1-band' else processed.filter_bands(load_bands)

        # STEP 3: Stretch the visual range
        min_val = params['min']
        max_val = params['max']
        
        # Scale to continuous percentage instead of 8-bit
        stretched_cube = final_cube.linear_scale_range(min_val, max_val, 0, 1)

        # STEP 4: Color mapping (Earth Engine "palette" behavior)
        if params['mode'] == '1-band' and ramp != 'gray':
            if ramp == 'viridis':
                r_band = stretched_cube * 0.2 + 0.1
                g_band = stretched_cube * 0.8 + 0.1
                b_band = 1.0 - stretched_cube
            elif ramp == 'rdylgn':
                r_band = 1.0 - stretched_cube
                g_band = stretched_cube
                b_band = stretched_cube * 0.2
            else: 
                r_band = stretched_cube
                g_band = stretched_cube
                b_band = stretched_cube

            # 🛠️ FIX: Add the missing "bands" dimension before merging to stop the Spark failure
            r_band = r_band.add_dimension(name="bands", label="R", type="bands")
            g_band = g_band.add_dimension(name="bands", label="G", type="bands")
            b_band = b_band.add_dimension(name="bands", label="B", type="bands")

            # Merge stacked bands into a unified RGB image
            final_image = r_band.merge_cubes(g_band).merge_cubes(b_band)
            
            # Map percentage float channels back to 0-255 spectrum for PNG delivery
            final_image = final_image.linear_scale_range(0, 1, 0, 255)
        else:
            # If it's already an RGB or grayscale request, scale natively to PNG bounds
            final_image = final_cube.linear_scale_range(min_val, max_val, 0, 255)

        print("[STYLE] Downloading processed visual PNG...")
        img_bytes = conn.download(final_image.save_result(format="PNG"))

        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        return {"image": f"data:image/png;base64,{base64_img}"}

    except Exception as e:
        print("❌ Styling error:")
        traceback.print_exc()
        return {"error": str(e)}


def get_raster_metadata(data):
    print("\n--- [BACKEND] Fetching Metadata ---")
    print(f"[INPUT] {data}")

    try:
        conn = get_connection()
        print("[STEP 1] Connected")

        is_calc = data.get('type') == 'calc'
        expression = data.get('expression')

        # --- Determine bands ---
        if is_calc and expression:
            bands = list(set(re.findall(r'"([^"]*)"', expression)))
            print(f"[STEP 2] Calc bands: {bands}")
        else:
            bands = data.get('bands', ["B04", "B03", "B02"])
            print(f"[STEP 2] Bands: {bands}")

        # --- Load cube ---
        print("[STEP 3] Loading collection...")
        cube = conn.load_collection(
            collection_id=data['collection'],
            spatial_extent=data['aoi'],
            temporal_extent=data['dates'],
            bands=bands
        )

        # --- Reduce time ---
        print("[STEP 4] Reducing temporal dimension...")
        cube = cube.reduce_dimension(dimension="t", reducer="median")

        # --- Apply calculation if needed ---
        if is_calc and expression:
            print("[STEP 5] Applying expression...")
            clean_expr = expression.replace('"', '')
            bands_dict = {band: cube.band(band) for band in bands}
            cube = eval(clean_expr, {"__builtins__": None}, bands_dict)
        else:
            print("[STEP 5] Selecting first band...")
            cube = cube.band(bands[0])

        # --- 💥 CRITICAL: DOWNSAMPLE BEFORE DOWNLOAD ---
        print("[STEP 6] Downsampling for histogram...")
        cube = cube.resample_spatial(resolution=100)  # reduces data size massively

        # --- Download as NetCDF ---
        print("[STEP 7] Downloading NetCDF...")
        bytes_data = conn.download(cube.save_result(format="NetCDF"))

        print("[STEP 8] Parsing NetCDF...")

        ds = xr.open_dataset(io.BytesIO(bytes_data), engine="h5netcdf")

        print("[DEBUG] Dataset variables:", list(ds.data_vars))

        # ✅ Select the correct data variable (ignore 'crs')
        data_var = None
        for var in ds.data_vars:
            if var.lower() != "crs":
                data_var = var
                break

        if data_var is None:
            raise Exception("No valid raster band found in dataset")

        print(f"[DEBUG] Using variable: {data_var}")

        values = ds[data_var].values

        # Flatten safely
        values = values.flatten()

        print(f"[DEBUG] Raw values count: {len(values)}")

        # ✅ Convert to float before isnan
        values = values.astype(np.float32)

        # Remove NaNs
        values = values[~np.isnan(values)]

        print(f"[DEBUG] Valid values count: {len(values)}")

        # Compute histogram
        hist, _ = np.histogram(values, bins=20)

        print(f"[DEBUG] Histogram: {hist.tolist()}")

        return {
            "bands": bands,
            "crs": "EPSG:4326",
            "resolution": "10m" if "SENTINEL2" in data.get('collection', '') else "20m",
            "histogram": hist.tolist()
        }

    except Exception as e:
        print("\n❌❌❌ METADATA ERROR ❌❌❌")
        print(f"Error: {str(e)}")
        traceback.print_exc()
        return {"error": str(e)}
