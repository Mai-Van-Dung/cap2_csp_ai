const stripTrailingSlash = (value) => value.replace(/\/+$/, "");

const getBrowserHostBase = (port) => {
  if (typeof window === "undefined" || !window.location?.hostname) {
    return `http://localhost:${port}`;
  }

  const { protocol, hostname } = window.location;
  return `${protocol}//${hostname}:${port}`;
};

export const BACKEND_BASE_URL = stripTrailingSlash(
  import.meta.env.VITE_BACKEND_BASE_URL || getBrowserHostBase(5000),
);

export const USER_API_URL = stripTrailingSlash(
  import.meta.env.VITE_USER_API_URL || `${getBrowserHostBase(5001)}/api/users`,
);

export const ALERTS_API_URL = stripTrailingSlash(
  import.meta.env.VITE_ALERTS_API_URL || `${BACKEND_BASE_URL}/api/alerts`,
);

export const VIDEO_FEED_URL = stripTrailingSlash(
  import.meta.env.VITE_VIDEO_FEED_URL || `${BACKEND_BASE_URL}/video_feed`,
);

export const ADMIN_CAMERA_GRID_URL = stripTrailingSlash(
  import.meta.env.VITE_ADMIN_CAMERA_GRID_URL ||
    `${BACKEND_BASE_URL}/api/admin/cameras/grid`,
);

export const cameraVideoFeedUrl = (cameraId) =>
  `${BACKEND_BASE_URL}/api/video_feed/${cameraId}`;
