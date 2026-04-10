/**
 * Zone Configuration Component
 * Allows user to view, create, and manage hazard zones
 * 
 * Features:
 * - Display live video feed with zones drawn
 * - Add/edit/delete zones
 * - Configure detection settings (min_child_height, sensitivity)
 * - Save zone configuration to backend
 */

import React, { useState, useEffect, useRef } from 'react';
import { saveZoneConfig, loadZoneConfig, deleteZone } from '../api/zone_service';
import { VIDEO_FEED_URL } from '../../../config/serviceUrls';

const ZoneConfigComponent = ({ cameraId = 1 }) => {
    const [zones, setZones] = useState([]);
    const [settings, setSettings] = useState({
        min_child_height: 50,
        sensitivity: 0.75
    });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [editingZone, setEditingZone] = useState(null);
    const videoRef = useRef(null);

    // Load zones on component mount
    useEffect(() => {
        loadZonesFromDB();
    }, [cameraId]);

    // Load video stream
    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.src = VIDEO_FEED_URL;
        }
    }, []);

    const loadZonesFromDB = async () => {
        setLoading(true);
        try {
            const data = await loadZoneConfig(cameraId);
            setZones(data);
            setError(null);
        } catch (err) {
            setError(`Failed to load zones: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveZones = async () => {
        setLoading(true);
        try {
            const response = await saveZoneConfig(cameraId, zones, settings);
            if (response.status === 'success') {
                setSuccess('Zone configuration saved successfully!');
                setTimeout(() => setSuccess(null), 3000);
            } else {
                setError(response.message);
            }
        } catch (err) {
            setError(`Failed to save zones: ${err.message}`);
        } finally {
            setLoading(false);
        }
    };

    const handleAddZone = () => {
        const newZoneId = `DPZ-${String(zones.length + 1).padStart(2, '0')}`;
        const newZone = {
            id: newZoneId,
            name: `Zone ${zones.length + 1}`,
            vertices: [
                [0.1, 0.1],
                [0.3, 0.1],
                [0.3, 0.3],
                [0.1, 0.3]
            ]
        };
        setZones([...zones, newZone]);
        setEditingZone(newZoneId);
    };

    const handleDeleteZone = async (zoneId) => {
        if (confirm(`Are you sure you want to delete zone ${zoneId}?`)) {
            try {
                const response = await deleteZone(zoneId, cameraId);
                if (response.status === 'success') {
                    setZones(zones.filter(z => z.id !== zoneId));
                    setSuccess('Zone deleted successfully!');
                    setTimeout(() => setSuccess(null), 3000);
                }
            } catch (err) {
                setError(`Failed to delete zone: ${err.message}`);
            }
        }
    };

    const handleUpdateZone = (zoneId, field, value) => {
        setZones(zones.map(zone =>
            zone.id === zoneId
                ? { ...zone, [field]: value }
                : zone
        ));
    };

    const handleUpdateVertex = (zoneId, vertexIndex, coordinate, value) => {
        setZones(zones.map(zone => {
            if (zone.id === zoneId) {
                const newVertices = zone.vertices.map((vertex, idx) => {
                    if (idx === vertexIndex) {
                        return [
                            coordinate === 'x' ? parseFloat(value) : vertex[0],
                            coordinate === 'y' ? parseFloat(value) : vertex[1]
                        ];
                    }
                    return vertex;
                });
                return { ...zone, vertices: newVertices };
            }
            return zone;
        }));
    };

    const handleSettingsChange = (field, value) => {
        setSettings({
            ...settings,
            [field]: field === 'sensitivity' ? parseFloat(value) : parseInt(value)
        });
    };

    return (
        <div style={styles.container}>
            <h2>Zone Configuration</h2>

            {/* Error Message */}
            {error && <div style={styles.error}>{error}</div>}
            {success && <div style={styles.success}>{success}</div>}

            <div style={styles.mainContent}>
                {/* Video Feed */}
                <div style={styles.videoSection}>
                    <h3>Live Video Feed</h3>
                    <img
                        ref={videoRef}
                        style={styles.video}
                        alt="Video Feed"
                    />
                    <p style={styles.hint}>
                        Zones will be displayed as orange polygons on the video
                    </p>
                </div>

                {/* Configuration Panel */}
                <div style={styles.configSection}>
                    {/* Detection Settings */}
                    <div style={styles.settingsGroup}>
                        <h4>Detection Settings</h4>
                        <div style={styles.formGroup}>
                            <label>Min Child Height (pixels)</label>
                            <input
                                type="number"
                                value={settings.min_child_height}
                                onChange={(e) => handleSettingsChange('min_child_height', e.target.value)}
                                min="10"
                                max="300"
                                style={styles.input}
                            />
                        </div>
                        <div style={styles.formGroup}>
                            <label>Sensitivity (0.0 - 1.0)</label>
                            <input
                                type="number"
                                value={settings.sensitivity}
                                onChange={(e) => handleSettingsChange('sensitivity', e.target.value)}
                                min="0"
                                max="1"
                                step="0.05"
                                style={styles.input}
                            />
                        </div>
                    </div>

                    {/* Zones List */}
                    <div style={styles.zonesGroup}>
                        <div style={styles.zonesHeader}>
                            <h4>Zones</h4>
                            <button
                                onClick={handleAddZone}
                                style={styles.addButton}
                                disabled={loading}
                            >
                                + Add Zone
                            </button>
                        </div>

                        {zones.length === 0 ? (
                            <p style={styles.noZones}>No zones configured. Click "Add Zone" to create one.</p>
                        ) : (
                            <div style={styles.zonesList}>
                                {zones.map(zone => (
                                    <div key={zone.id} style={styles.zoneCard}>
                                        <div style={styles.zoneHeader}>
                                            <h5>{zone.id}</h5>
                                            <button
                                                onClick={() => handleDeleteZone(zone.id)}
                                                style={styles.deleteButton}
                                            >
                                                Delete
                                            </button>
                                        </div>

                                        <div style={styles.formGroup}>
                                            <label>Zone Name</label>
                                            <input
                                                type="text"
                                                value={zone.name}
                                                onChange={(e) => handleUpdateZone(zone.id, 'name', e.target.value)}
                                                style={styles.input}
                                            />
                                        </div>

                                        <div style={styles.verticesGroup}>
                                            <label>Vertices (normalized 0-1):</label>
                                            {zone.vertices.map((vertex, idx) => (
                                                <div key={idx} style={styles.vertexRow}>
                                                    <span style={styles.vertexLabel}>Point {idx + 1}:</span>
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        max="1"
                                                        step="0.05"
                                                        value={vertex[0]}
                                                        onChange={(e) =>
                                                            handleUpdateVertex(zone.id, idx, 'x', e.target.value)
                                                        }
                                                        placeholder="X"
                                                        style={styles.coordinateInput}
                                                    />
                                                    <input
                                                        type="number"
                                                        min="0"
                                                        max="1"
                                                        step="0.05"
                                                        value={vertex[1]}
                                                        onChange={(e) =>
                                                            handleUpdateVertex(zone.id, idx, 'y', e.target.value)
                                                        }
                                                        placeholder="Y"
                                                        style={styles.coordinateInput}
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Save Button */}
                    <button
                        onClick={handleSaveZones}
                        style={styles.saveButton}
                        disabled={loading}
                    >
                        {loading ? 'Saving...' : 'Save Configuration'}
                    </button>
                </div>
            </div>
        </div>
    );
};

const styles = {
    container: {
        padding: '20px',
        fontFamily: 'Arial, sans-serif',
        backgroundColor: '#f5f5f5',
        minHeight: '100vh'
    },
    error: {
        backgroundColor: '#f8d7da',
        color: '#721c24',
        padding: '12px',
        borderRadius: '4px',
        marginBottom: '15px',
        border: '1px solid #f5c6cb'
    },
    success: {
        backgroundColor: '#d4edda',
        color: '#155724',
        padding: '12px',
        borderRadius: '4px',
        marginBottom: '15px',
        border: '1px solid #c3e6cb'
    },
    mainContent: {
        display: 'flex',
        gap: '20px',
        flexWrap: 'wrap'
    },
    videoSection: {
        flex: '1 1 60%',
        minWidth: '300px',
        backgroundColor: '#fff',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
    },
    video: {
        width: '100%',
        maxWidth: '100%',
        height: 'auto',
        backgroundColor: '#000',
        borderRadius: '4px',
        marginBottom: '10px'
    },
    hint: {
        fontSize: '12px',
        color: '#666',
        margin: '10px 0 0 0'
    },
    configSection: {
        flex: '1 1 35%',
        minWidth: '300px',
        backgroundColor: '#fff',
        padding: '20px',
        borderRadius: '8px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
        maxHeight: '80vh',
        overflowY: 'auto'
    },
    settingsGroup: {
        marginBottom: '20px',
        paddingBottom: '20px',
        borderBottom: '1px solid #eee'
    },
    zonesGroup: {
        marginBottom: '20px'
    },
    zonesHeader: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '15px'
    },
    addButton: {
        padding: '8px 12px',
        backgroundColor: '#28a745',
        color: '#fff',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '14px'
    },
    zonesList: {
        display: 'flex',
        flexDirection: 'column',
        gap: '15px',
        marginBottom: '15px',
        maxHeight: '400px',
        overflowY: 'auto'
    },
    zoneCard: {
        backgroundColor: '#f9f9f9',
        border: '1px solid #ddd',
        borderRadius: '4px',
        padding: '15px',
        marginBottom: '10px'
    },
    zoneHeader: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '10px'
    },
    deleteButton: {
        padding: '6px 10px',
        backgroundColor: '#dc3545',
        color: '#fff',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '12px'
    },
    formGroup: {
        marginBottom: '12px'
    },
    input: {
        width: '100%',
        padding: '8px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        fontSize: '14px',
        boxSizing: 'border-box'
    },
    verticesGroup: {
        marginTop: '10px',
        padding: '10px',
        backgroundColor: '#f0f0f0',
        borderRadius: '4px'
    },
    vertexRow: {
        display: 'flex',
        gap: '8px',
        marginBottom: '8px',
        alignItems: 'center'
    },
    vertexLabel: {
        minWidth: '70px',
        fontSize: '12px',
        color: '#666'
    },
    coordinateInput: {
        width: '60px',
        padding: '6px',
        border: '1px solid #ddd',
        borderRadius: '4px',
        fontSize: '12px'
    },
    noZones: {
        color: '#999',
        fontStyle: 'italic',
        padding: '20px',
        textAlign: 'center'
    },
    saveButton: {
        width: '100%',
        padding: '12px',
        backgroundColor: '#007bff',
        color: '#fff',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '16px',
        fontWeight: 'bold',
        marginTop: '20px'
    }
};

export default ZoneConfigComponent;
