"""
Zone service module for handling zone configuration and retrieval from database
"""
import json
import logging
from db_connector import fetch_all, fetch_one, execute_query

logger = logging.getLogger(__name__)


def save_zone_config(camera_id, zones, settings):
    """
    Save zone configuration from React frontend to database.
    If zone id exists, perform UPDATE. Otherwise, perform INSERT.
    
    Args:
        camera_id (int): Camera ID
        zones (list): List of zone objects with id, name, vertices
        settings (dict): Contains min_child_height and sensitivity
    
    Returns:
        dict: Status and message
    """
    try:
        for zone in zones:
            zone_id = zone.get("id")
            zone_name = zone.get("name")
            vertices = zone.get("vertices", [])
            min_child_height = settings.get("min_child_height", 50)
            sensitivity = settings.get("sensitivity", 0.75)
            
            # Check if zone already exists
            existing = fetch_one(
                "SELECT id FROM zones WHERE id = %s AND camera_id = %s",
                (zone_id, camera_id)
            )
            
            if existing:
                # UPDATE existing zone
                query = """
                    UPDATE zones 
                    SET zone_name = %s, 
                        coordinates = %s, 
                        min_child_height = %s, 
                        sensitivity = %s
                    WHERE id = %s AND camera_id = %s
                """
                execute_query(
                    query,
                    (
                        zone_name,
                        json.dumps(vertices),
                        min_child_height,
                        sensitivity,
                        zone_id,
                        camera_id
                    )
                )
                logger.info(f"Updated zone {zone_id} for camera {camera_id}")
            else:
                # INSERT new zone
                query = """
                    INSERT INTO zones 
                    (id, camera_id, zone_name, coordinates, min_child_height, sensitivity, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                execute_query(
                    query,
                    (
                        zone_id,
                        camera_id,
                        zone_name,
                        json.dumps(vertices),
                        min_child_height,
                        sensitivity,
                        True
                    )
                )
                logger.info(f"Inserted new zone {zone_id} for camera {camera_id}")
        
        return {
            "status": "success",
            "message": f"Successfully saved {len(zones)} zone(s)",
            "zones_count": len(zones)
        }
    except Exception as e:
        logger.error(f"Error saving zone config: {e}")
        return {
            "status": "error",
            "message": f"Error saving zones: {str(e)}"
        }


def load_zones(camera_id):
    """
    Load all zones for a specific camera from database.
    
    Args:
        camera_id (int): Camera ID
    
    Returns:
        list: List of zone objects with coordinates and settings
    """
    try:
        zones = fetch_all(
            """SELECT id, zone_name, coordinates, min_child_height, sensitivity 
               FROM zones 
               WHERE camera_id = %s AND is_active = TRUE
               ORDER BY id""",
            (camera_id,)
        )
        
        # Parse JSON coordinates for each zone
        for zone in zones:
            if zone.get("coordinates"):
                try:
                    zone["coordinates"] = json.loads(zone["coordinates"])
                except json.JSONDecodeError:
                    zone["coordinates"] = []
            else:
                zone["coordinates"] = []
        
        logger.info(f"Loaded {len(zones)} zones for camera {camera_id}")
        return zones
    except Exception as e:
        logger.error(f"Error loading zones for camera {camera_id}: {e}")
        return []


def get_zone_settings(camera_id, zone_id):
    """
    Get specific zone settings (min_child_height, sensitivity)
    
    Args:
        camera_id (int): Camera ID
        zone_id (str): Zone ID (e.g., "DPZ-01")
    
    Returns:
        dict: Zone settings or None if not found
    """
    try:
        zone = fetch_one(
            """SELECT min_child_height, sensitivity 
               FROM zones 
               WHERE id = %s AND camera_id = %s""",
            (zone_id, camera_id)
        )
        return zone
    except Exception as e:
        logger.error(f"Error getting zone settings for {zone_id}: {e}")
        return None


def delete_zone(zone_id, camera_id):
    """
    Delete a zone from database
    
    Args:
        zone_id (str): Zone ID
        camera_id (int): Camera ID
    
    Returns:
        dict: Status message
    """
    try:
        execute_query(
            "DELETE FROM zones WHERE id = %s AND camera_id = %s",
            (zone_id, camera_id)
        )
        logger.info(f"Deleted zone {zone_id} for camera {camera_id}")
        return {
            "status": "success",
            "message": f"Zone {zone_id} deleted"
        }
    except Exception as e:
        logger.error(f"Error deleting zone: {e}")
        return {
            "status": "error",
            "message": f"Error deleting zone: {str(e)}"
        }
