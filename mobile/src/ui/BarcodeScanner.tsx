import { CameraView, useCameraPermissions } from "expo-camera";
import { useRef, useState } from "react";
import {
  ActivityIndicator,
  Platform,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";

import { formStyles as s } from "./formStyles";

/**
 * The formats actually printed on food packaging. Restricting the list keeps
 * the scanner from firing on QR codes and shipping labels that happen to be
 * in frame.
 */
const FOOD_BARCODE_TYPES = ["ean13", "ean8", "upc_a", "upc_e"] as const;

interface BarcodeScannerProps {
  onScanned: (barcode: string) => void;
  onCancel: () => void;
  /** Shown over the camera while the scanned code is being looked up. */
  isBusy?: boolean;
}

export function BarcodeScanner({
  onScanned,
  onCancel,
  isBusy = false,
}: BarcodeScannerProps): React.JSX.Element {
  const [permission, requestPermission] = useCameraPermissions();
  const [isRequesting, setIsRequesting] = useState(false);
  // The camera fires onBarcodeScanned continuously while a code is in frame,
  // so without this the parent would get dozens of lookups for one scan.
  const hasScanned = useRef(false);

  if (Platform.OS === "web") {
    return (
      <View style={[s.card, { gap: 8 }]}>
        <Text style={s.error}>Barcode scanning needs a real camera.</Text>
        <Text style={s.helpText}>
          Open Fitora on your phone to scan, or search for the food by name here.
        </Text>
        <TouchableOpacity onPress={onCancel}>
          <Text style={s.secondaryButtonText}>Back to search</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (!permission) {
    return (
      <View style={[s.card, { alignItems: "center" }]}>
        <ActivityIndicator />
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={[s.card, { gap: 8 }]}>
        <Text style={s.helpText}>
          Fitora needs camera access to read barcodes. The camera is used only to find the
          barcode — nothing is recorded and no image leaves your phone.
        </Text>
        {permission.canAskAgain ? (
          <TouchableOpacity
            style={[s.button, { marginTop: 0 }]}
            onPress={() => {
              setIsRequesting(true);
              void requestPermission().finally(() => setIsRequesting(false));
            }}
          >
            {isRequesting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={s.buttonText}>Allow camera</Text>
            )}
          </TouchableOpacity>
        ) : (
          <Text style={s.error}>
            Camera access is turned off for Fitora. Enable it in your device settings, or
            search for the food by name instead.
          </Text>
        )}
        <TouchableOpacity onPress={onCancel}>
          <Text style={s.secondaryButtonText}>Back to search</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={{ gap: 8 }}>
      <View
        style={{
          height: 260,
          borderRadius: 12,
          overflow: "hidden",
          backgroundColor: "#000",
        }}
      >
        <CameraView
          style={{ flex: 1 }}
          facing="back"
          barcodeScannerSettings={{ barcodeTypes: [...FOOD_BARCODE_TYPES] }}
          onBarcodeScanned={({ data }) => {
            if (hasScanned.current || isBusy) return;
            hasScanned.current = true;
            onScanned(data);
          }}
        />
        {isBusy ? (
          <View
            style={[
              StyleSheet.absoluteFill,
              {
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: "rgba(0,0,0,0.45)",
              },
            ]}
          >
            <ActivityIndicator color="#fff" size="large" />
          </View>
        ) : null}
      </View>

      <Text style={s.helpText}>Point the camera at the barcode on the package.</Text>

      <View style={{ flexDirection: "row", gap: 16 }}>
        <TouchableOpacity onPress={onCancel}>
          <Text style={s.secondaryButtonText}>Cancel</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={() => {
            hasScanned.current = false;
          }}
        >
          <Text style={s.secondaryButtonText}>Scan again</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
