/* Use case: Lets a person sign in to or create an Osalytix account from the phone.
What it does: Calls the live register and login endpoints, stores the session securely and opens the web reset page for forgotten passwords. */

import { useState } from "react";
import { KeyboardAvoidingView, Linking, Platform, Pressable, Text, View } from "react-native";
import { api, saveToken, SITE } from "../api";
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
        {mode === "login" && (
          <Pressable onPress={() => Linking.openURL(`${SITE}/reset`)} accessibilityRole="link">
            <Text style={{ color: color.saffronInk, fontWeight: "600", textAlign: "center" }}>Forgot your password?</Text>
          </Pressable>
        )}
        <Receipt title="What you get" stamp="EXACT">
          <P>Upload a file, ask in your own words, and every number is calculated from your data — never guessed by the AI.</P>
        </Receipt>
        <P muted>Google sign-in works on the website. Accounts are shared between the website and this app.</P>
      </Screen>
    </KeyboardAvoidingView>
  );
}
