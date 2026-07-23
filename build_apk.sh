#!/usr/bin/env bash
# =============================================================================
#  build_apk.sh — Build an Android APK wrapper for AI Agent Beast
# =============================================================================
#  This script creates a lightweight Android WebView APK that points to the
#  agent's web dashboard. It uses the "PWA-to-APK" approach via a simple
#  Chrome PWA wrapper, or falls back to building a Termux bootstrap APK.
#
#  Requirements:
#    - Android SDK / Build Tools (or use the cloud build option)
#    - Java JDK 11+
#    - Python + git
#
#  Usage:
#    bash build_apk.sh [--dashboard-url https://your-tunnel.trycloudflare.com]
#
#  If no URL is provided, defaults to http://localhost:8765
# =============================================================================

set -e

BLUE='\033[0;34m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'

DASHBOARD_URL="${1:-http://localhost:8765}"
APP_NAME="AI Agent Beast"
PACKAGE_NAME="com.agent.beast"
OUTPUT_DIR="dist"

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       AI Agent Beast — Android APK Builder                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${CYAN}Dashboard URL:${NC} $DASHBOARD_URL"
echo -e "  ${CYAN}App Name:${NC}      $APP_NAME"
echo -e "  ${CYAN}Package:${NC}       $PACKAGE_NAME"
echo ""

# ---- Detect environment ----------------------------------------------------
echo -e "${YELLOW}[1/4] Checking build environment...${NC}"

HAS_SDK=0
HAS_BUNDLETOOL=0
HAS_JAVA=0

if command -v java &>/dev/null; then HAS_JAVA=1; fi
if [ -n "$ANDROID_HOME" ] || [ -n "$ANDROID_SDK_ROOT" ]; then HAS_SDK=1; fi
if command -v bundletool &>/dev/null; then HAS_BUNDLETOOL=1; fi

# ---- Method 1: Bubblewrap / PWA Builder (requires SDK) --------------------
if [ "$HAS_SDK" -eq 1 ] && [ "$HAS_JAVA" -eq 1 ]; then
    echo -e "${GREEN}  → Android SDK + Java detected. Using PWABuilder method.${NC}"

    if ! command -v bubblewrap &>/dev/null; then
        echo -e "${YELLOW}  → Installing @bubblewrap/cli via npx...${NC}"
    fi

    mkdir -p "$OUTPUT_DIR"
    npx -y @bubblewrap/cli init \
        --manifest "$DASHBOARD_URL/manifest.json" \
        --directory "$OUTPUT_DIR/pwa-build" \
        2>/dev/null || {
        echo -e "${YELLOW}  → Bubblewrap init failed; falling back to manual APK.${NC}"
        HAS_SDK=0
    }

    if [ -d "$OUTPUT_DIR/pwa-build" ]; then
        cd "$OUTPUT_DIR/pwa-build"
        npx -y @bubblewrap/cli build 2>&1
        cd ../..
        APK_FILE=$(find "$OUTPUT_DIR/pwa-build" -name "*.apk" | head -1)
        if [ -f "$APK_FILE" ]; then
            cp "$APK_FILE" "$OUTPUT_DIR/agent-beast.apk"
            echo -e "${GREEN}✅ APK built: $OUTPUT_DIR/agent-beast.apk${NC}"
            exit 0
        fi
    fi
fi

# ---- Method 2: Create a simple Termux bootstrap APK script ----------------
echo -e "${YELLOW}[2/4] No Android SDK available. Creating deploy script + APK instructions.${NC}"

mkdir -p "$OUTPUT_DIR"

# Generate a minimal AndroidManifest.xml for manual build
cat > "$OUTPUT_DIR/AndroidManifest.xml" << XML
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="$PACKAGE_NAME"
    android:versionCode="1"
    android:versionName="1.0">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />

    <application
        android:label="$APP_NAME"
        android:allowBackup="true"
        android:usesCleartextTraffic="true">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:theme="@style/Theme.AppCompat.Light.NoActionBar">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>
XML

cat > "$OUTPUT_DIR/MainActivity.java" << JAVACLASS
package $PACKAGE_NAME;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebSettings;

public class MainActivity extends Activity {
    private WebView webView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        webView = new WebView(this);
        setContentView(webView);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowContentAccess(true);
        settings.setAllowFileAccess(true);

        webView.setWebViewClient(new WebViewClient());
        webView.loadUrl("$DASHBOARD_URL");
    }

    @Override
    public void onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }
}
JAVACLASS

echo -e "${YELLOW}[3/4] Creating build helper script...${NC}"

cat > "$OUTPUT_DIR/build_android.sh" << 'BUILDSCRIPT'
#!/usr/bin/env bash
# Build the APK manually using Android SDK command-line tools.
# Prerequisites:
#   - Android SDK command-line tools installed
#   - Set ANDROID_SDK_ROOT to your SDK path
#   - Build tools version 34+ installed via sdkmanager

set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
PACKAGE="com.agent.beast"
APP_NAME="AI Agent Beast"
DASHBOARD_URL="${1:-http://192.168.1.100:8765}"

SDK="${ANDROID_SDK_ROOT:-$HOME/Android/Sdk}"
BUILD_TOOLS="$SDK/build-tools/34.0.0"
PLATFORM="$SDK/platforms/android-34"

# Replace URL in source
sed -i "s|webView.loadUrl(\".*\");|webView.loadUrl(\"$DASHBOARD_URL\");|" "$DIR/MainActivity.java"

# Compile
javac -cp "$PLATFORM/android.jar" -d "$DIR/classes" "$DIR/MainActivity.java"

# DEX
"$BUILD_TOOLS/dx" --dex --output="$DIR/classes.dex" "$DIR/classes"

# Package resources
"$BUILD_TOOLS/aapt2" compile -o "$DIR/res.zip" --dir "$DIR/res" 2>/dev/null || true

# Build APK
"$BUILD_TOOLS/aapt2" link -o "$DIR/unaligned.apk" \
    -I "$PLATFORM/android.jar" \
    --manifest "$DIR/AndroidManifest.xml" \
    $([ -f "$DIR/res.zip" ] && echo "-R $DIR/res.zip") \
    --auto-add-overlay

# Add DEX
cd "$DIR"
"$BUILD_TOOLS/aapt2" add unaligned.apk classes.dex

# Align & sign
"$BUILD_TOOLS/zipalign" -f 4 unaligned.apk agent-beast.apk

# Generate debug key if needed
if [ ! -f debug.keystore ]; then
    keytool -genkey -v -keystore debug.keystore \
        -alias androiddebugkey -keyalg RSA -keysize 2048 \
        -validity 10000 -storepass android -keypass android \
        -dname "CN=Debug, OU=Android, O=Agent, L=City, ST=State, C=US"
fi

"$BUILD_TOOLS/apksigner" sign --ks debug.keystore \
    --ks-pass pass:android --key-pass pass:android \
    --out agent-beast.apk agent-beast.apk

rm -f unaligned.apk classes.dex
echo "✅ APK built: $DIR/agent-beast.apk"
BUILDSCRIPT

chmod +x "$OUTPUT_DIR/build_android.sh"

# ---- Summary ---------------------------------------------------------------
echo -e "${YELLOW}[4/4] Final output${NC}"
echo ""
echo -e "${GREEN}┌─────────────────────────────────────────────────────────────┐${NC}"
echo -e "${GREEN}│  ✅ APK Build Preparation Complete                          │${NC}"
echo -e "${GREEN}│                                                             │${NC}"
echo -e "${GREEN}│  📱 Option 1: Cloud Build                                   │${NC}"
echo -e "${GREEN}│     Use https://app.pwabuilder.com/ with URL:                │${NC}"
echo -e "${GREEN}│       $DASHBOARD_URL                    │${NC}"
echo -e "${GREEN}│                                                             │${NC}"
echo -e "${GREEN}│  📱 Option 2: Manual Build                                  │${NC}"
echo -e "${GREEN}│     cd $OUTPUT_DIR && bash build_android.sh                  │${NC}"
echo -e "${GREEN}│                                                             │${NC}"
echo -e "${GREEN}│  📱 Option 3: Termux                                        │${NC}"
echo -e "${GREEN}│     Run: bash deploy_phone.sh --web                          │${NC}"
echo -e "${GREEN}└─────────────────────────────────────────────────────────────┘${NC}"
echo ""
echo -e "  ${CYAN}Source files in:${NC} $OUTPUT_DIR/"
echo -e "  ${CYAN}  - AndroidManifest.xml${NC}"
echo -e "  ${CYAN}  - MainActivity.java${NC}"
echo -e "  ${CYAN}  - build_android.sh${NC}"
