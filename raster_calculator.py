#!/usr/bin/env python3
import openeo
import os
import base64
import re
import traceback
from dotenv import load_dotenv

# Ensure environment variables are loaded for this file
load_dotenv()

def run_math_index(aoi, dates, collection, expression):
    try:
        print(f"\n---- [BACKEND] Starting Pixel Calculation of {collection} ----")
        
        print("STEP 1: Connecting to CDSE API...")
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu/")

        print("STEP 2: Authenticating...")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )
        print("SUCCESS: Authenticated")

        # 1. Extract band names from quotes
        required_bands = list(set(re.findall(r'"([^"]*)"', expression)))
        print(f"STEP 3: Bands detected from expression: {required_bands}")

        # 2. Load Cube
        print(f"STEP 4: Loading the collection {collection}")
        cube = connection.load_collection(
            collection_id=collection,
            spatial_extent=aoi,
            temporal_extent=dates,
            bands=required_bands
        )

        print("STEP 4b: Downsampling for stability...")
        # cube = cube.resample_spatial(resolution=60)

        # 3. Processing
        print("STEP 5: Reducing dimension (Median)...")
        processed = cube.reduce_dimension(dimension="t", reducer="median")
        
        print("STEP 6: Applying Map Algebra via Python Eval...")
        # Clean the expression for Python: remove quotes around band names
        # e.g., '("B04" - "B03")' becomes '(B04 - B03)'
        clean_expr = expression.replace('"', '')
        print(f"   Expression: {clean_expr}")

        # Create a dictionary mapping band names to actual OpenEO band objects
        # This allows us to use standard Python operators like - / +
        bands_dict = {band: processed.band(band) for band in required_bands}
        
        # Execute the math. 
        # OpenEO's Python client handles (band_obj1 - band_obj2) by building the process graph
        index_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)

        # 4. Scaling & Download
        print("STEP 7: Linear scaling range (-1 to 1 -> 0 to 255)...")
        # Most spectral indices range from -1 to 1. We scale for PNG visibility.
        visual_cube = index_cube.linear_scale_range(-1, 1, 0, 255)
        
        print("STEP 8: Starting PNG Download from Copernicus...")
        img_bytes = connection.download(visual_cube.save_result(format="PNG"))
        print(f"STEP 9: Download complete. Bytes received: {len(img_bytes)}")

        base64_img = base64.b64encode(img_bytes).decode('utf-8')
        print("SUCCESS: Image encoded to Base64.")

        return {
            "image": f"data:image/png;base64,{base64_img}",
            "aoi": aoi
        }

    except Exception as e:
        print(f"❌ CRITICAL ERROR in raster_calculator: {str(e)}")
        traceback.print_exc()
        return {"error": str(e), "image": None}
