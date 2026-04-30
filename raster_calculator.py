#!/usr/bin/env python3
import openeo
import os
import base64
import re
import traceback
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

def run_math_index(aoi, dates, collection, expression):
    try:
        print(f"\n---- [BACKEND] Starting Pixel Calculation of {collection} ----")
        
        # 1. Connection & Auth
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu/")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )

        # 2. Parse Expression
        required_bands = list(set(re.findall(r'"([^"]*)"', expression)))
        
        # 3. Load Cube
        cube = connection.load_collection(
            collection_id=collection,
            spatial_extent=aoi,
            temporal_extent=dates,
            bands=required_bands
        )

        # 4. Processing
        processed = cube.reduce_dimension(dimension="t", reducer="median")
        
        # Clean expression for evaluation
        clean_expr = expression.replace('"', '')
        bands_dict = {band: processed.band(band) for band in required_bands}
        
        # OpenEO Python client builds the process graph from standard operators
        index_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)

        # 5. Visual Scaling
        # Spectral indices like NDVI (-1 to 1) are scaled to 0-255 for PNG display
        visual_cube = index_cube.linear_scale_range(-1, 1, 0, 255)
        
        # 6. Download & Encode
        img_bytes = connection.download(visual_cube.save_result(format="PNG"))
        base64_img = base64.b64encode(img_bytes).decode('utf-8')

        return {
            "image": f"data:image/png;base64,{base64_img}",
            "aoi": aoi,
            # CRITICAL: Return metadata stating there is only 1 band named "Index"
            "metadata": {
                "bands": ["Index"],
                "type": "calc"
            }
        }

    except Exception as e:
        print(f"❌ ERROR in raster_calculator: {str(e)}")
        traceback.print_exc()
        return {"error": str(e), "image": None}
