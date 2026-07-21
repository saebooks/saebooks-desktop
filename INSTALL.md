# Installing SAE Books / tasur on your computer

This guide is for everyday users. No technical knowledge needed.

SAE Books (and its Estonian edition, **tasur**) is free software. The
desktop app on this page is the full product — there are no locked
features, trials, or payment prompts.

The desktop app is the window onto your books. Your books themselves live
on a **server** — either on this same computer (if you or someone helping
you installed the one-click server) or somewhere else (another computer at
your office, or an online address someone gave you). The app asks about
this once, the first time it starts, and remembers your answer.

---

## Linux

**Download** the file for your product:

- SAE Books: `SAEBooks-0.4.0-x86_64.AppImage`
- tasur: `tasur-0.4.0-x86_64.AppImage`

An AppImage is a program in a single file — nothing to install.

1. Find the downloaded file (usually in your **Downloads** folder).
2. Right-click it → **Properties** → **Permissions** → tick
   **"Allow executing file as program"** (on some systems this is a
   switch labelled "Executable"). You only do this once.
3. Double-click the file. The app opens.

If double-clicking does nothing, your system may be missing one common
component. Open a terminal and run `sudo apt install libfuse2`, then
double-click again. (This is the only technical step you might ever need.)

### First run — three short questions

1. **Where is your server?**
   - *On this computer* — pick this if the server was installed on this
     same machine. The app finds it by itself; just press
     **Test Connection**.
   - *Online server* — pick this if you were given a web address
     (it looks like `https://books.example.com`). Type it in and press
     **Test Connection**.
   - *Server on my home or office network* — an advanced option; the
     person who set up your server will tell you if you need it.
2. **Sign in** with the email and password for your books account.
3. **Pick your company** (most people have just one) and press Finish.

That's it — you won't see these questions again.

### Updating

Download the new AppImage, make it executable the same way, and delete the
old file. Your books and settings are kept — they live on the server, not
in the app file.

---

## Windows

**Download** the installer for your product:

- SAE Books: `SAEBooks-0.4.0-x64.msi`
- tasur: `tasur-0.4.0-x64.msi`

1. Double-click the downloaded `.msi`.
2. Windows will likely show a blue **"Windows protected your PC"**
   (SmartScreen) screen. This is expected: SAE Books is beta software and
   the installer is not yet code-signed, so Windows doesn't recognise the
   publisher. Click **More info**, then **Run anyway**.
3. Follow the installer (Next → Next → Finish). It puts the app in your
   Start menu and on your desktop.

Start the app from the Start menu or the desktop shortcut. To remove it
later, use **Settings → Apps** like any other program.

### First run — three short questions

Same as Linux below: where is your server, sign in, pick your company.

## Mac

**Download** the disk image for your product:

- SAE Books: `SAE Books-0.4.0.dmg`
- tasur: `tasur-0.4.0.dmg`

1. Open the `.dmg` and drag the app into **Applications**.
2. The app is beta software and not yet notarized with Apple, so
   double-clicking the first time may be blocked. Instead,
   **right-click (or Control-click) the app → Open → Open**. You only do
   this once; afterwards it opens normally.

---

## Checking your download (optional)

If you want to verify the file arrived intact, compare its SHA-256
checksum against `SHA256SUMS-0.4.0.txt` published alongside the
downloads:

```
sha256sum SAEBooks-0.4.0-x86_64.AppImage
```

The long code it prints must match the one in the checksum file exactly.
