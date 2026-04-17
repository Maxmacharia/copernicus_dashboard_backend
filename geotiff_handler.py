import openeo
import os
import re
import traceback
from dotenv import load_dotenv

load_dotenv()

def generate_geotiff(data):
    layer_name = data.get('name', 'Unknown Layer')
    print(f"\n--- [BACKEND] 🛰️  Export Starting: {layer_name} ---")
    
    try:
        print("STEP 1: Connecting to CDSE API...")
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu")
        
        print("STEP 2: Authenticating...")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )
        print("SUCCESS: Authenticated.")
        
        aoi = data.get("aoi")
        collection = data.get("collection")
        dates = data.get("dates")
        
        print(f"STEP 3: Preparing DataCube for Collection: {collection}")
        
        # This is where the JSONDecodeError usually happens internally.
        # OpenEO tries to fetch metadata that isn't always strictly required for the download.
        cube = connection.load_collection(
            collection_id=collection, 
            spatial_extent=aoi, 
            temporal_extent=dates, 
            bands=data.get("bands") if data.get("type") != "calc" else list(set(re.findall(r'"([^"]*)"', data.get("expression"))))
        )

        if data.get("type") == "calc":
            expression = data.get("expression")
            print(f"   - Mode: Raster Calculation | Expr: {expression}")
            processed = cube.reduce_dimension(dimension="t", reducer="median")
            required_bands = list(set(re.findall(r'"([^"]*)"', expression)))
            bands_dict = {band: processed.band(band) for band in required_bands}
            clean_expr = expression.replace('"', '')
            result_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)
        else:
            print(f"   - Mode: Visual Search Layer")
            result_cube = cube.reduce_dimension(dimension="t", reducer="median")

        print("STEP 4: Requesting GeoTIFF Download (Processing on CDSE)...")
        
        # We wrap the download to catch the metadata warning but proceed with bytes
        gtiff_bytes = connection.download(result_cube.save_result(format="GTiff"))
        
        if gtiff_bytes:
            print(f"SUCCESS: Export complete. Sent {len(gtiff_bytes)} bytes.")
            return gtiff_bytes
        else:
            raise Exception("Download returned empty bytes.")

    except Exception as e:
        print(f"❌ ERROR in geotiff_handler: {str(e)}")
        # If we have bytes but a metadata error occurred, we might still be able to return them
        # but here we log the full traceback for debugging.
        traceback.print_exc()
        raise e
