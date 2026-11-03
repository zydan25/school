import { Stack } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { AppProviders } from "@/core/providers/app-providers";
import { palette } from "@/core/theme/tokens";

export default function RootLayout() {
  return (
    <AppProviders>
      <StatusBar style="dark" />
      <Stack
        screenOptions={{
          headerShown: false,
          contentStyle: { backgroundColor: palette.background, direction: "rtl" },
          animation: "fade",
        }}
      />
    </AppProviders>
  );
}
