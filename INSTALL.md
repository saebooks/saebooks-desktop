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

- SAE Books: `SAEBooks-0.3.0-x86_64.AppImage`
- tasur: `tasur-0.3.0-x86_64.AppImage`

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

A Windows installer (`.msi` — download, double-click, Next-Next-Finish) is
prepared but **not yet published**: it has to be built and tested on a
Windows machine, which hasn't happened yet. It will appear here when it is
real. Until then Windows users can use the web app in their browser at the
same server address.

## Mac

There is **no Mac version yet**. Mac users can use the web app in their
browser at the same server address. A proper Mac app is planned.

---

## Checking your download (optional)

If you want to verify the file arrived intact, compare its SHA-256
checksum against `SHA256SUMS-0.3.0.txt` published alongside the
downloads:

```
sha256sum SAEBooks-0.3.0-x86_64.AppImage
```

The long code it prints must match the one in the checksum file exactly.
