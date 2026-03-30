/**
 * Zone Configuration Service
 * This module provides functions to interact with the Flask Zone API
 *
 * Usage in React components:
 * import { zoneService } from './zoneService.js'
 */

const API_BASE_URL = "http://localhost:5000";

/**
 * Save zone configuration to the backend
 * @param {number} cameraId - The camera ID
 * @param {Array} zones - Array of zone objects with id, name, vertices
 * @param {Object} settings - Detection settings (min_child_height, sensitivity)
 * @returns {Promise<Object>} Response from server
 */
export const saveZoneConfig = async (cameraId, zones, settings = {}) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/save_config`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        camera_id: cameraId,
        zones: zones,
        settings: {
          min_child_height: settings.min_child_height || 50,
          sensitivity: settings.sensitivity || 0.75,
          ...settings, // Spread additional settings
        },
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Save zone config error:", error);
    throw error;
  }
};

/**
 * Load zone configuration from the backend
 * @param {number} cameraId - The camera ID
 * @returns {Promise<Array>} Array of zone objects
 */
export const loadZoneConfig = async (cameraId) => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/load_zones/${cameraId}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.status === "success") {
      return data.zones || [];
    } else {
      throw new Error(data.message || "Failed to load zones");
    }
  } catch (error) {
    console.error("Load zone config error:", error);
    throw error;
  }
};

/**
 * Delete a specific zone
 * @param {string} zoneId - The zone ID (e.g., 'DPZ-01')
 * @param {number} cameraId - The camera ID
 * @returns {Promise<Object>} Response from server
 */
export const deleteZone = async (zoneId, cameraId) => {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/delete_zone/${zoneId}/${cameraId}`,
      { method: "DELETE" },
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error("Delete zone error:", error);
    throw error;
  }
};

/**
 * Normalize pixel coordinates to 0-1 range
 * @param {number} pixelValue - Pixel value
 * @param {number} frameSize - Frame dimension (width or height)
 * @returns {number} Normalized value (0-1)
 */
export const normalizeCoordinate = (pixelValue, frameSize) => {
  return pixelValue / frameSize;
};

/**
 * Convert normalized coordinates to pixel coordinates
 * @param {number} normalizedValue - Normalized value (0-1)
 * @param {number} frameSize - Frame dimension (width or height)
 * @returns {number} Pixel value
 */
export const denormalizeCoordinate = (normalizedValue, frameSize) => {
  return normalizedValue * frameSize;
};

/**
 * Convert a polygon of normalized vertices to pixel coordinates
 * @param {Array} normalizedVertices - Array of [x, y] normalized coordinates
 * @param {number} frameWidth - Frame width in pixels
 * @param {number} frameHeight - Frame height in pixels
 * @returns {Array} Array of [x, y] pixel coordinates
 */
export const normalizePolygon = (
  normalizedVertices,
  frameWidth,
  frameHeight,
) => {
  return normalizedVertices.map(([x, y]) => [
    denormalizeCoordinate(x, frameWidth),
    denormalizeCoordinate(y, frameHeight),
  ]);
};

/**
 * Example zone configuration object
 */
export const exampleZoneConfig = {
  cameraId: 1,
  zones: [
    {
      id: "DPZ-01",
      name: "Pool Zone",
      vertices: [
        [0.1, 0.2], // Top-left
        [0.4, 0.2], // Top-right
        [0.4, 0.6], // Bottom-right
        [0.1, 0.6], // Bottom-left
      ],
    },
    {
      id: "DPZ-02",
      name: "Playground Zone",
      vertices: [
        [0.5, 0.3],
        [0.9, 0.3],
        [0.9, 0.9],
        [0.5, 0.9],
      ],
    },
  ],
  settings: {
    min_child_height: 50,
    sensitivity: 0.75,
  },
};

/**
 * Example React Hook for manage zones
 *
 * Usage in React component:
 * const { zones, loading, error, saveZones, loadZones } = useZoneConfig(cameraId);
 */
export const useZoneConfig = (cameraId) => {
  const [zones, setZones] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState(null);

  const loadZones = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await loadZoneConfig(cameraId);
      setZones(data);
      setError(null);
    } catch (err) {
      setError(err.message);
      setZones([]);
    } finally {
      setLoading(false);
    }
  }, [cameraId]);

  const saveZones = React.useCallback(
    async (zonesData, settings) => {
      setLoading(true);
      try {
        const response = await saveZoneConfig(cameraId, zonesData, settings);
        if (response.status === "success") {
          setZones(zonesData);
          setError(null);
          return response;
        } else {
          throw new Error(response.message);
        }
      } catch (err) {
        setError(err.message);
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [cameraId],
  );

  const removeZone = React.useCallback(
    async (zoneId) => {
      try {
        const response = await deleteZone(zoneId, cameraId);
        if (response.status === "success") {
          setZones(zones.filter((z) => z.id !== zoneId));
        } else {
          throw new Error(response.message);
        }
      } catch (err) {
        setError(err.message);
        throw err;
      }
    },
    [cameraId, zones],
  );

  // Load zones on mount
  React.useEffect(() => {
    loadZones();
  }, [loadZones]);

  return {
    zones,
    loading,
    error,
    loadZones,
    saveZones,
    removeZone,
  };
};
