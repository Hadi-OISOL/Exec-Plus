> **File use case:** How to run the Osalytix phone app.
> **What it does:** Explains starting the Expo server, scanning it with Expo Go and which live API it uses.

# Osalytix phone app (Expo / React Native)

Talks directly to the live Osalytix API: `https://syntelio.173-208-151-137.sslip.io/api`
(set in `src/api.ts`). Accounts are the same as on the website.

## Run and scan

```bash
cd apps/mobile
npm install
npx expo start --tunnel ngrok   # works from any network
# or: npx expo start            # phone and computer on the same Wi-Fi
```

Install **Expo Go** on the phone, then scan the QR code (Android: inside Expo Go;
iPhone: with the Camera app). Expo Go must support SDK 58.

## What is in the app

- Sign in / create account (email + password), get-to-know-you questions
- Files: upload any supported file (up to 500 MB) or a fictional sample
- File questions first (units from a suggested-unit list), then insights and the auto dashboard
- Ask Osalytix: chat with exact tables, bars, follow-ups and clarification choices
- Chat history, plan usage and sign out

Forecasts, what-if scenarios, exports, connectors and team settings stay on the website for now.

## Checks

```bash
npx tsc --noEmit
npx expo export --platform android --output-dir /tmp/osalytix-export
```
