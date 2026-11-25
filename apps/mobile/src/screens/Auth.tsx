/* Use case: Lets a person sign in to or create an Osalytix account from the phone.
What it does: Calls the live register and login endpoints, stores the session securely and opens the web reset page for forgotten passwords. */

import * as Crypto from "expo-crypto";
import * as Linking from "expo-linking";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import Svg, { Path } from "react-native-svg";
import { KeyboardAvoidingView, Platform, Pressable, Text, View } from "react-native";
import { api, API, saveToken, SITE } from "../api";
import { color, space } from "../theme";
import { Button, Chip, ErrorText, Field, P, Receipt, Screen, s } from "../ui";

export function AuthScreen({ onSignedIn }: { onSignedIn: () => void }) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function google() {
    setError("");
    setBusy(true);
    try {
      const bytes = Crypto.getRandomBytes(48);
      const urlSafe = (b64: string) => b64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
      const verifier = urlSafe(btoa(String.fromCharCode(...bytes)));
      const challenge = urlSafe(
        await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, verifier, { encoding: Crypto.CryptoEncoding.BASE64 }),
      );
      const returnTo = Linking.createURL("auth");
      const start = `${API}/auth/google/start?return_to=${encodeURIComponent(returnTo)}&challenge=${challenge}`;
      const result = await WebBrowser.openAuthSessionAsync(start, returnTo);
      if (result.type !== "success") return setError(`Google sign-in was not finished. If it keeps failing, this app address may need to be allowed: ${returnTo}`);
      const params = Linking.parse(result.url).queryParams ?? {};
      if (!params.handoff) return setError("Google sign-in did not complete. Please try again.");
      const exchanged = await api<{ token?: string; error?: string }>("/auth/oauth/exchange", {
        body: { handoff: String(params.handoff), verifier },
      });
      if (!exchanged.token)
        return setError(
          exchanged.error === "google_identity_conflict"
            ? "This email already has a password account. Sign in with your password."
            : "Google sign-in could not be completed.",
        );
      await saveToken(exchanged.token);
      onSignedIn();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Google sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    setError("");
    if (!email.trim() || !password) return setError("Enter your email and password.");
    if (mode === "signup" && password.length < 15) return setError("Use a password of at least 15 characters.");
    setBusy(true);
    try {
      if (mode === "signup")
        await api("/auth/register", {
          body: {
            email: email.trim(),
            password,
            display_name: name.trim() || email.split("@")[0],
            workspace_name: company.trim() || `${name.trim() || "My"} workspace`,
          },
        });
      const result = await api<{ token: string }>("/auth/login", { body: { email: email.trim(), password } });
      await saveToken(result.token);
      onSignedIn();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Screen kicker="Every number comes with a receipt" title={mode === "login" ? "Welcome back." : "Make your account."}>
        <View style={[s.row, { marginBottom: space(1) }]}>
          <Chip label="Sign in" active={mode === "login"} onPress={() => setMode("login")} />
          <Chip label="Create account" active={mode === "signup"} onPress={() => setMode("signup")} />
        </View>
        {mode === "signup" && (
          <>
            <Field label="Your name" value={name} onChangeText={setName} autoComplete="name" />
            <Field label="Company or team" value={company} onChangeText={setCompany} />
          </>
        )}
        <Field
          label="Email"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          autoComplete="email"
          keyboardType="email-address"
        />
        <Field
          label="Password"
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          autoComplete={mode === "login" ? "current-password" : "new-password"}
          onSubmitEditing={submit}
        />
        <ErrorText text={error} />
        <Button label={mode === "login" ? "Sign in" : "Create account"} onPress={submit} busy={busy} />
        <Text style={{ textAlign: "center", color: color.muted }}>or</Text>
        <Pressable
          onPress={busy ? undefined : google}
          accessibilityRole="button"
          accessibilityLabel="Continue with Google"
          style={({ pressed }) => [s.button, s.secondary, { flexDirection: "row", gap: space(3), borderColor: color.line, backgroundColor: color.white }, (pressed || busy) && { opacity: 0.7 }]}
        >
          <GoogleMark />
          <Text style={[s.buttonText, { color: color.ink }]}>Continue with Google</Text>
        </Pressable>
        {mode === "login" && (
          <Pressable onPress={() => WebBrowser.openBrowserAsync(`${SITE}/reset`)} accessibilityRole="link">
            <Text style={{ color: color.saffronInk, fontWeight: "600", textAlign: "center" }}>Forgot your password?</Text>
          </Pressable>
        )}
        <Receipt title="What you get" stamp="EXACT">
          <P>Upload a file, ask in your own words, and every number is calculated from your data — never guessed by the AI.</P>
        </Receipt>
        <P muted>Accounts are shared between the website and this app.</P>
      </Screen>
    </KeyboardAvoidingView>
  );
}

function GoogleMark() {
  return (
    <Svg width={20} height={20} viewBox="0 0 48 48" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z" />
      <Path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z" />
      <Path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z" />
      <Path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z" />
    </Svg>
  );
}
