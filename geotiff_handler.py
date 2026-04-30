import openeo
import os
import re
import traceback
from dotenv import load_dotenv

load_dotenv()

def generate_geotiff(data):
    layer_name = data.get('name', 'Export_Layer')
    print(f"\n--- [BACKEND] 🛰️  Exporting: {layer_name} ---")
    
    try:
        connection = openeo.connect("https://openeo.dataspace.copernicus.eu/")
        connection.authenticate_oidc_client_credentials(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET")
        )
        
        aoi = data.get("aoi")
        collection = data.get("collection")
        dates = data.get("dates")
        
        # Determine required bands based on whether it is a calculation or standard layer
        bands = data.get("bands")
        if data.get("type") == "calc":
            bands = list(set(re.findall(r'"([^"]*)"', data.get("expression"))))

        cube = connection.load_collection(
            collection_id=collection, 
            spatial_extent=aoi, 
            temporal_extent=dates, 
            bands=bands
        )

        # SPEED FIX: Use 'mean' instead of 'median' for exports. 
        # Median requires sorting the entire stack, while mean is a simple accumulation.
        print(f"STEP: Processing temporal reduction (MEAN)...")
        result_cube = cube.reduce_dimension(dimension="t", reducer="mean")

        if data.get("type") == "calc":
            expression = data.get("expression")
            bands_dict = {band: result_cube.band(band) for band in bands}
            clean_expr = expression.replace('"', '')
            result_cube = eval(clean_expr, {"__builtins__": None}, bands_dict)

        print("STEP: Initiating GeoTIFF stream from CDSE...")
        # We use format="GTiff" and ensure no extra tiling overhead for standard downloads
        gtiff_bytes = connection.download(result_cube.save_result(format="GTiff"))
        
        if gtiff_bytes:
            print(f"SUCCESS: Export complete ({len(gtiff_bytes)} bytes).")
            return gtiff_bytes
        else:
            raise Exception("CDSE returned empty data.")

    except Exception as e:
        print(f"❌ EXPORT ERROR: {str(e)}")
        traceback.print_exc()
        raise e
