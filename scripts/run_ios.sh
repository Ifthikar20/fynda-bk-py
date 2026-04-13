#!/bin/bash
set -e

# ──────────────────────────────────────────────────────────────
# Outfi iOS — Build, configure Google Auth, and install on iPhone
# ──────────────────────────────────────────────────────────────

FLUTTER_DIR="$(cd "$(dirname "$0")/../Flutter_outfi_app" && pwd)"
IOS_DIR="$FLUTTER_DIR/ios"
RUNNER_DIR="$IOS_DIR/Runner"
PLIST="$RUNNER_DIR/Info.plist"
GOOGLE_PLIST="$RUNNER_DIR/GoogleService-Info.plist"
API_CONFIG="$FLUTTER_DIR/lib/config/api_config.dart"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}╔══════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Outfi iOS — Build & Install Script     ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════╝${NC}"
echo ""

# ── Step 0: Check prerequisites ──────────────────────────────
echo -e "${YELLOW}[0/6] Checking prerequisites...${NC}"

if ! command -v flutter &>/dev/null; then
  echo -e "${RED}Error: Flutter not found. Install from https://docs.flutter.dev/get-started/install${NC}"
  exit 1
fi

if ! command -v xcodebuild &>/dev/null; then
  echo -e "${RED}Error: Xcode not found. Install from the App Store.${NC}"
  exit 1
fi

if ! command -v pod &>/dev/null; then
  echo -e "${RED}Error: CocoaPods not found. Install with: sudo gem install cocoapods${NC}"
  exit 1
fi

flutter --version
echo -e "${GREEN}All prerequisites OK.${NC}"
echo ""

# ── Step 1: Google Cloud setup check ─────────────────────────
echo -e "${YELLOW}[1/6] Configuring Google Auth...${NC}"

if [ ! -f "$GOOGLE_PLIST" ]; then
  echo -e "${RED}┌──────────────────────────────────────────────────────────────┐${NC}"
  echo -e "${RED}│  GoogleService-Info.plist NOT FOUND                          │${NC}"
  echo -e "${RED}│                                                              │${NC}"
  echo -e "${RED}│  You need to set up a Google Cloud project first:            │${NC}"
  echo -e "${RED}│                                                              │${NC}"
  echo -e "${RED}│  1. Go to https://console.firebase.google.com               │${NC}"
  echo -e "${RED}│  2. Create a project (or use existing)                       │${NC}"
  echo -e "${RED}│  3. Add an iOS app with bundle ID: com.outfi.outfiApp       │${NC}"
  echo -e "${RED}│  4. Download GoogleService-Info.plist                        │${NC}"
  echo -e "${RED}│  5. Place it at:                                             │${NC}"
  echo -e "${RED}│     Flutter_outfi_app/ios/Runner/GoogleService-Info.plist    │${NC}"
  echo -e "${RED}│                                                              │${NC}"
  echo -e "${RED}│  Then in Google Cloud Console:                               │${NC}"
  echo -e "${RED}│  6. Go to APIs & Services > Credentials                     │${NC}"
  echo -e "${RED}│  7. Find the iOS client ID (auto-created by Firebase)        │${NC}"
  echo -e "${RED}│  8. Note the Client ID and Reversed Client ID               │${NC}"
  echo -e "${RED}│                                                              │${NC}"
  echo -e "${RED}│  Also create a Web client ID (for serverClientId):           │${NC}"
  echo -e "${RED}│  9. Create OAuth 2.0 Client ID > Web application             │${NC}"
  echo -e "${RED}│  10. Note this Web Client ID                                │${NC}"
  echo -e "${RED}└──────────────────────────────────────────────────────────────┘${NC}"
  echo ""
  echo -e "${CYAN}Do you have the GoogleService-Info.plist ready? (y/n)${NC}"
  read -r HAS_PLIST

  if [ "$HAS_PLIST" != "y" ] && [ "$HAS_PLIST" != "Y" ]; then
    echo -e "${YELLOW}Skipping Google Auth setup. You can run this script again after setup.${NC}"
    echo -e "${YELLOW}The app will still build but Google Sign-In will not work.${NC}"
    SKIP_GOOGLE=true
  else
    echo -e "${CYAN}Enter the path to your GoogleService-Info.plist:${NC}"
    read -r PLIST_PATH
    if [ -f "$PLIST_PATH" ]; then
      cp "$PLIST_PATH" "$GOOGLE_PLIST"
      echo -e "${GREEN}GoogleService-Info.plist copied.${NC}"
    else
      echo -e "${RED}File not found: $PLIST_PATH${NC}"
      echo -e "${YELLOW}Continuing without Google Auth...${NC}"
      SKIP_GOOGLE=true
    fi
  fi
else
  echo -e "${GREEN}GoogleService-Info.plist found.${NC}"
fi

# ── Step 2: Extract and apply Google credentials ─────────────
if [ "$SKIP_GOOGLE" != "true" ] && [ -f "$GOOGLE_PLIST" ]; then
  echo -e "${YELLOW}[2/6] Applying Google Auth credentials...${NC}"

  # Extract values from GoogleService-Info.plist
  REVERSED_CLIENT_ID=$(/usr/libexec/PlistBuddy -c "Print :REVERSED_CLIENT_ID" "$GOOGLE_PLIST" 2>/dev/null || echo "")
  IOS_CLIENT_ID=$(/usr/libexec/PlistBuddy -c "Print :CLIENT_ID" "$GOOGLE_PLIST" 2>/dev/null || echo "")
  BUNDLE_ID=$(/usr/libexec/PlistBuddy -c "Print :BUNDLE_ID" "$GOOGLE_PLIST" 2>/dev/null || echo "")

  if [ -z "$REVERSED_CLIENT_ID" ] || [ -z "$IOS_CLIENT_ID" ]; then
    echo -e "${RED}Could not extract credentials from GoogleService-Info.plist${NC}"
    echo -e "${YELLOW}Continuing without Google Auth URL scheme...${NC}"
  else
    echo -e "${GREEN}  iOS Client ID: ${IOS_CLIENT_ID:0:30}...${NC}"
    echo -e "${GREEN}  Reversed Client ID: $REVERSED_CLIENT_ID${NC}"

    # Add URL scheme to Info.plist for Google Sign-In callback
    if ! /usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes" "$PLIST" &>/dev/null; then
      /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes array" "$PLIST"
    fi

    # Check if Google URL scheme already exists
    SCHEME_EXISTS=false
    URL_TYPES_COUNT=$(/usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes" "$PLIST" 2>/dev/null | grep -c "Dict" || echo "0")
    for ((i=0; i<URL_TYPES_COUNT; i++)); do
      EXISTING=$(/usr/libexec/PlistBuddy -c "Print :CFBundleURLTypes:$i:CFBundleURLSchemes:0" "$PLIST" 2>/dev/null || echo "")
      if [ "$EXISTING" = "$REVERSED_CLIENT_ID" ]; then
        SCHEME_EXISTS=true
        break
      fi
    done

    if [ "$SCHEME_EXISTS" = false ]; then
      /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0 dict" "$PLIST"
      /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleTypeRole string Editor" "$PLIST"
      /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "$PLIST"
      /usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string $REVERSED_CLIENT_ID" "$PLIST"
      echo -e "${GREEN}  Added Google URL scheme to Info.plist${NC}"
    else
      echo -e "${GREEN}  Google URL scheme already in Info.plist${NC}"
    fi

    # Prompt for Web Client ID (used as serverClientId for backend auth code exchange)
    CURRENT_GOOGLE_ID=$(grep "googleClientId" "$API_CONFIG" | grep -oP"'[^']*'" | tr -d "'" || echo "")
    if [ -z "$CURRENT_GOOGLE_ID" ]; then
      echo ""
      echo -e "${CYAN}Enter your Google Web Client ID (for server-side auth code exchange):${NC}"
      echo -e "${CYAN}(Find this in Google Cloud Console > APIs & Services > Credentials > Web client)${NC}"
      read -r WEB_CLIENT_ID
      if [ -n "$WEB_CLIENT_ID" ]; then
        sed -i '' "s|static const String googleClientId = '';|static const String googleClientId = '$WEB_CLIENT_ID';|" "$API_CONFIG"
        echo -e "${GREEN}  Updated googleClientId in api_config.dart${NC}"
      fi
    else
      echo -e "${GREEN}  googleClientId already set in api_config.dart${NC}"
    fi
  fi
else
  echo -e "${YELLOW}[2/6] Skipping Google Auth credentials (no plist).${NC}"
fi

echo ""

# ── Step 3: Flutter dependencies ─────────────────────────────
echo -e "${YELLOW}[3/6] Installing Flutter dependencies...${NC}"
cd "$FLUTTER_DIR"

# Dart-define secrets (override with env vars)
OUTFI_API_KEY="${OUTFI_MOBILE_API_KEY:-A-wkfUfqEj864To5QA2QsRavy4yphfDsfuhiGiY1h2E}"
STRIPE_KEY="${STRIPE_PUBLISHABLE_KEY:-pk_test_placeholder}"
GOOGLE_ID="${GOOGLE_CLIENT_ID:-placeholder}"

DART_DEFINES=(
  --dart-define=OUTFI_MOBILE_API_KEY="$OUTFI_API_KEY"
  --dart-define=STRIPE_PUBLISHABLE_KEY="$STRIPE_KEY"
  --dart-define=GOOGLE_CLIENT_ID="$GOOGLE_ID"
)

flutter pub get
echo -e "${GREEN}Flutter dependencies installed.${NC}"
echo ""

# ── Step 4: iOS Pod install ──────────────────────────────────
echo -e "${YELLOW}[4/6] Installing CocoaPods dependencies...${NC}"
cd "$IOS_DIR"
pod install --repo-update
echo -e "${GREEN}Pods installed.${NC}"
echo ""

# ── Step 5: Detect connected iPhone ──────────────────────────
echo -e "${YELLOW}[5/6] Detecting connected iPhone...${NC}"
cd "$FLUTTER_DIR"

DEVICES=$(flutter devices 2>/dev/null)
echo "$DEVICES"
echo ""

# Check for physical iOS device
if echo "$DEVICES" | grep -qi "iphone"; then
  DEVICE_ID=$(flutter devices 2>/dev/null | grep -i "iphone" | head -1 | grep -oP '[a-f0-9\-]{20,}' || echo "")
  if [ -n "$DEVICE_ID" ]; then
    echo -e "${GREEN}Found iPhone: $DEVICE_ID${NC}"
  else
    echo -e "${YELLOW}iPhone detected but could not extract device ID.${NC}"
    echo -e "${YELLOW}Will use default device selection.${NC}"
  fi
else
  echo -e "${YELLOW}No physical iPhone detected. Available options:${NC}"
  echo -e "${YELLOW}  1. Connect your iPhone via USB and trust the computer${NC}"
  echo -e "${YELLOW}  2. Will fall back to iOS Simulator${NC}"
  echo ""
  echo -e "${CYAN}Continue with simulator? (y/n)${NC}"
  read -r USE_SIM
  if [ "$USE_SIM" != "y" ] && [ "$USE_SIM" != "Y" ]; then
    echo -e "${RED}Please connect your iPhone and run the script again.${NC}"
    exit 1
  fi
  # Boot simulator
  echo -e "${YELLOW}Booting iOS Simulator...${NC}"
  open -a Simulator 2>/dev/null || true
  sleep 3
fi

echo ""

# ── Step 6: Build and install ────────────────────────────────
echo -e "${YELLOW}[6/6] Building and installing on device...${NC}"
cd "$FLUTTER_DIR"

if [ -n "$DEVICE_ID" ]; then
  flutter run --release "${DART_DEFINES[@]}" -d "$DEVICE_ID"
else
  flutter run --release "${DART_DEFINES[@]}"
fi

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   Outfi app installed successfully!      ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
