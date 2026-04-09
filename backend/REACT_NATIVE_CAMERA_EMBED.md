# React Native Camera Embed (User App)

This backend now exposes a WebView-friendly route:

- `GET /viewer/camera`
- Stream source inside page: `GET /video_feed` (MJPEG)

Use the React Native screen below in your user app.

## 1) Install dependency

```bash
npm install react-native-webview
```

## 2) Replace camera section in your HomeScreen

```jsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { WebView } from 'react-native-webview';

const API_BASE_URL = 'http://192.168.1.100:5000';

export default function CameraEmbedCard() {
	const viewerUrl = `${API_BASE_URL}/viewer/camera?label=Camera%20chinh`;

	return (
		<View style={styles.cameraCard}>
			<View style={styles.liveBadge}>
				<View style={styles.liveDot} />
				<Text style={styles.liveText}>LIVE</Text>
			</View>

			<View style={styles.cameraFeed}>
				<WebView
					source={{ uri: viewerUrl }}
					style={styles.webview}
					allowsInlineMediaPlayback
					mediaPlaybackRequiresUserAction={false}
					javaScriptEnabled
					domStorageEnabled
					startInLoadingState
					originWhitelist={['*']}
					scrollEnabled={false}
				/>
			</View>
		</View>
	);
}

const styles = StyleSheet.create({
	cameraCard: {
		backgroundColor: '#1A2A3A',
		margin: 16,
		marginBottom: 0,
		borderRadius: 20,
		overflow: 'hidden',
	},
	liveBadge: {
		position: 'absolute',
		top: 12,
		right: 12,
		zIndex: 10,
		flexDirection: 'row',
		alignItems: 'center',
		backgroundColor: '#E53935',
		borderRadius: 12,
		paddingHorizontal: 10,
		paddingVertical: 4,
		gap: 4,
	},
	liveDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: '#FFF' },
	liveText: { color: '#FFF', fontWeight: '800', fontSize: 11, letterSpacing: 1 },
	cameraFeed: {
		height: 220,
		backgroundColor: '#243447',
	},
	webview: {
		flex: 1,
		backgroundColor: '#243447',
	},
});
```

## 3) Important network note

- Do not use `localhost` on phone.
- Replace `API_BASE_URL` with your backend machine LAN IP, for example `http://192.168.1.100:5000`.
- Phone and backend machine must be on the same network.

## 4) Quick verify

Open this URL in phone browser first:

- `http://192.168.1.100:5000/viewer/camera`

If browser sees LIVE camera, WebView in app will also work.

