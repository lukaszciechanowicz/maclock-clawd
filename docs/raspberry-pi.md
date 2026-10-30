# Raspberry Pi: configuration, changes and operations

[Back to README](../README.md) · [API cookbook](api.md) · [Claude Code integration](claude-code.md)

This guide records the deployed Maclock device and the changes made while provisioning, repairing and deploying it. It separates existing Imager/user settings from assistant changes. Provisioning commands are for a new or repaired system; do not blindly reapply them to the working Pi. Ordinary API requests need neither SSH nor sudo.

## Device and verified runtime

| Item | Installed device |
| --- | --- |
| Board | Original Raspberry Pi Zero W, ARMv6 / `armv6l`; not Zero 2 W |
| OS | Raspbian GNU/Linux 13.6, Trixie; reference image dated 2026-10-06 |
| Display | Waveshare **2.8inch DPI LCD**, SKU **18628**, capacitive Goodix touch; native **480 × 640** |
| Display connection | GPIO/DPI666 video; touch uses software I²C |
| Application scene | **640 × 480** landscape; application `--rotation 90` maps it to the physical panel |
| Hostname / administrator | `maclock` / `lukasz`, originally provisioned by Imager |
| Current Wi-Fi LAN address | `192.168.1.57/24`; user changed it from `192.168.1.212` |
| USB gadget address | `usb0`, `10.12.194.1/28`, managed by the official USB gadget/NetworkManager setup |
| Native API | `http://192.168.1.57:8765`, bearer authentication required for `/api/*` and `/hooks/*` |
| Rendering | Python 3.13, pygame 2.6.1, SDL KMSDRM and VC4 GLES2; no desktop/browser on the Pi |

No router/DHCP-reservation change was made by the application deployment. Do not treat the current LAN address as a portable default for another installation. The Wi-Fi badge reports radio/link association, not Internet reachability; a working USB link is not evidence that Wi-Fi is connected.

### Relevant installed packages

Package versions were read from the installed device; they are an inventory, not an instruction to pin every future OS update.

| Package | Observed version |
| --- | --- |
| `python3` | `3.13.5-1` |
| `python3-pygame` | `2.6.1-1+b2` |
| `python3-gpiozero` | `2.0.1` |
| `python3-lgpio` | `0.2.2` |
| `libgbm1`, `libgl1-mesa-dri` | `26.2.2-1~bpo13+0~rpt1` |
| `libegl1`, `libgles2` | `1.7.0-1` |
| `libdrm2` | `2.4.134-3~bpo13+1+rpt1` |
| `fontconfig` | `2.15.0-2.3` |
| `fonts-dejavu-core` | `2.37-8` |
| `locales` | `2.41-12+rpt1+deb13u4` |
| `openssh-server` | `1:10.0p1-7+deb13u4` |
| `device-tree-compiler` | `1.7.2-2+b1` |
| `libsdl2-2.0-0` | `2.32.4+dfsg-1` |
| `libdrm-tests` | `2.4.134-3~bpo13+1+rpt1` |

Runtime installation on a new compatible Raspberry Pi OS image uses distro packages, not a desktop pygame wheel built for a different ARM generation:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends python3-pygame libgbm1 libegl1 libgles2 libgl1-mesa-dri fontconfig fonts-dejavu-core
```

The actual native-install transaction explicitly requested `python3-pygame libgbm1 libegl1 libgles2 libgl1-mesa-dri libdrm-tests fonts-dejavu-core`: **66 packages were newly installed**, without upgrades/removals. `fontconfig` was installed afterward with two dependencies, bringing these transactions to **69 additions**. The [complete package/version ledger](raspberry-pi-packages.txt) records every addition, including transitive dependencies. `libdrm-tests` was a diagnostic tool, not a Python application dependency; add it separately when reproducing that diagnostic environment.

`python3-gpiozero` and `python3-lgpio` were already installed on this Pi before the button work. They are not new additions to the historical 69-package transaction or its ledger. Fresh systems need these distro GPIO packages for buttons (see below); no pip compiler build is needed.

Unreliable initial mirror downloads were worked around using per-command `Acquire::ForceIPv4=true`, verified HTTPS package downloads from `archive.raspbian.org` into `/var/cache/apt/archives`, and `apt-get --no-download`. Checksums came from APT metadata. **Package repository configuration was not changed**, and the temporary IPv4 flags were not installed as permanent APT settings.

SDL pulls in some X11/Wayland/audio libraries; that does not mean a desktop session was configured. Chromium, Node, Playwright and Pillow are not needed by the native application.

## Files, ownership and retained state

| Path | Purpose / access |
| --- | --- |
| `/boot/firmware/config.txt` | Firmware, DPI, touch and USB peripheral configuration |
| `/boot/firmware/cmdline.txt` | Single-line kernel command line; preserve this card's root identifier |
| `/boot/firmware/user-data` | Private Imager cloud-init data extended with the USB gadget flag and touch rule/reload actions; never commit the complete file |
| `/boot/firmware/overlays/vc4-kms-dpi-2inch8.dtbo` | Unmodified vendor display overlay |
| `/boot/firmware/overlays/waveshare-touch-28dpi.dtbo` | Unmodified vendor Goodix touch/backlight overlay |
| `/etc/udev/rules.d/99-waveshare-touch.rules` | Landscape libinput touch calibration |
| `/etc/default/locale`, `/etc/locale.gen` | System UTF-8 locale selection/generation |
| `/etc/locale.gen.maclock-backup` | Original locale-generation configuration before enabling missing US UTF-8, root-owned `0644` |
| `/opt/maclock-clawd` | Root-owned application source, directory mode `0755` |
| `/etc/systemd/system/pipclock.service` | Installed copy of [the repository unit](../deploy/pipclock.service) |
| `/etc/systemd/system/pipclock.service.pre-gles2` | Retained pre-fix unit, root-owned `0644`; **not** a known-good display rollback |
| `/etc/pipclock.env` | Root-owned mode `0600`: LAN host and secret bearer token; never commit |
| `/var/lib/pipclock` | Systemd-created state directory, `pipclock:pipclock`, mode `0700` |
| `/var/lib/pipclock/idle.json` | Atomic mode-`0600` idle playlist settings, owned by the service account |
| `/home/lukasz/maclock-redesign.RFLoD6` | Retained device-specific release archive, checksum, `install.sh` and private `lan.env`; not a second running service |
| `/opt/maclock-clawd.before-redesign.*` | Root-created application-source snapshots taken before release replacement |

The `pipclock` system account has home `/opt/maclock-clawd`, shell `/usr/sbin/nologin`, and the `video`, `render` and `input` supplementary groups. It is not the SSH administrator account. Its source directory remains root-owned; application writes go to the separate state directory.

These were the account/directory provisioning commands, for a **new** system only; do not recreate the existing account:

```sh
sudo useradd --system --user-group --home-dir /opt/maclock-clawd --no-create-home --shell /usr/sbin/nologin pipclock
sudo usermod -aG video,render,input pipclock
sudo install -d -o root -g root -m 0755 /opt/maclock-clawd
```

The retained staging `lan.env` is also secret. Do not publish its contents or copy it into a release archive. Source snapshots do **not** replace a backup of `/etc/pipclock.env` or `/var/lib/pipclock/idle.json`.

## Display and boot changes

### Firmware configuration

These changes were applied to the Imager-written boot partition. On the Mac it was mounted at `/Volumes/bootfs`; the running Pi exposes it as `/boot/firmware`.

Existing defaults were changed to:

```ini
dtparam=audio=off
camera_auto_detect=0
display_auto_detect=0
```

The display/USB settings under the applicable `[all]` section are:

```ini
enable_uart=0
dtoverlay=vc4-kms-dpi-2inch8
dtoverlay=waveshare-touch-28dpi
dtoverlay=dwc2,dr_mode=peripheral
```

Audio was disabled to leave PWM/GPIO resources available to the backlight. UART on GPIO14/15 was disabled because the DPI bus uses those pins. Camera/DSI autodetection was disabled for this fixed GPIO display.

Existing KMS settings were retained, including `dtoverlay=vc4-kms-v3d`, `max_framebuffers=2`, `auto_initramfs=1`, `disable_fw_kms_setup=1` and `disable_overscan=1`. Inherited `[cm4]`, `[cm5]` and `[pi5]` entries are not new Zero W settings. Do not copy board-specific host-mode blocks into the Zero W `[all]` section.

### Vendor overlays, not custom drivers

Two blobs were copied unchanged from the official [Waveshare overlay archive](https://files.waveshare.com/wiki/2.8inc-DPI-LCD/28DPI-DTBO.zip). The other board-specific overlays in that ZIP were not installed/enabled for this Zero W.

| Artifact | SHA-256 |
| --- | --- |
| `28DPI-DTBO.zip` | `abcf510709b33eb97eadf03c8df42211880106c7309ecfac47000992038c810b` |
| `vc4-kms-dpi-2inch8.dtbo` | `0d4575c83d69ad778e5010bbc6165b90b9242b25b7013e309a8db9e4b6b078d6` |
| `waveshare-touch-28dpi.dtbo` | `3f3591e498ce424ff04b6a24ff2edeb6535ac8f8f6fc9006ee7981129fa6174a` |

The installed blobs were compared against that archive again during documentation. No patched/recompiled vendor overlay is required by this deployment. If reinstalling, verify the archive and selected members before copying them to `/boot/firmware/overlays/`; a newer vendor ZIP may have different checksums and needs review rather than bypassing verification.

The selected touch overlay supplies Goodix GT911 nodes at `0x14`/`0x5d`, software I²C on GPIO10/11, IRQ GPIO27 and backlight GPIO18.

### Kernel command line

The following arguments were added, keeping `cmdline.txt` as **one line**:

```text
modules-load=dwc2,g_ether video=DPI-1:480x640M@60,rotate=90
```

`console=serial0,115200` was removed; `console=tty1` and the image's root/filesystem/cloud-init arguments were preserved. **Never copy another card's `root=PARTUUID=...` value.** Snapshots before and after first boot contain different root identifiers; the assistant preserved the then-current value rather than issuing a repartitioning command.

Kernel `video=...rotate=90` and application `--rotation 90` operate at different layers. The application still opens the native 480 × 640 mode, renders a 640 × 480 canvas and rotates it before presentation. Do not remove one rotation merely because the other exists.

### Touch calibration

The following root-owned mode-`0644` rule was provisioned through cloud-init and is present on the device:

```udev
ACTION=="add|change", SUBSYSTEM=="input", KERNEL=="event*", ATTRS{name}=="Goodix Capacitive TouchScreen", ENV{LIBINPUT_CALIBRATION_MATRIX}="0 -1 1 1 0 0"
```

After creating/changing that rule, the provisioning commands were:

```sh
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=input --action=change
```

This configures libinput's 90° calibration. Physical touch-axis alignment was not independently demonstrated; the application currently treats a touch anywhere as `knock`, not a position-dependent control.

The touch rule was added through `user-data`'s `write_files` with owner `root:root` and permissions `'0644'`. The reload/trigger commands above were appended to the **existing** `runcmd` list, not substituted for Imager's SSH/user setup. Preserve the other private cloud-init fields when reconstructing this provisioning step.

## Optional physical previous/next buttons

The existing application handles previous/next switches directly through `gpiozero.Button` and the LGPIO backend. There is no separate daemon, new HTTP endpoint, network round trip or SSH requirement for a press.

The [Waveshare pinout](https://www.waveshare.com/wiki/2.8inch_DPI_LCD#Pinout_Definition) marks physical header pins **35 and 37 as NC**, available to the user. They map to [BCM GPIO19](https://pinout.xyz/pinout/pin35_gpio19/) and [BCM GPIO26](https://pinout.xyz/pinout/pin37_gpio26/), respectively. The verified vendor overlays use GPIO10/11 for touch I²C, GPIO27 for its interrupt and GPIO18 for backlight; GPIO19/26 need not be reclaimed from touch.

| Function | BCM GPIO | Physical 40-pin header position |
| --- | --- | --- |
| Previous Clawd | GPIO19 | 35 |
| Next Clawd | GPIO26 | 37 |
| Shared ground | GND | 39 |

Use two **normally-open, voltage-free momentary contacts**, each connecting its GPIO to ground when pressed. The application enables internal 3.3 V pull-ups (`pull_up=True`), so released is high and pressed is low, with **50 ms debounce** (`bounce_time=0.05`). A held switch does not repeat. Do not connect GPIO to 5 V or to powered outputs from the clock's old circuit board. Disconnect power while wiring. If the case only supplies plastic button caps, fit microswitches underneath; if a switch has four legs, identify the actual switching pair with a meter rather than assuming every pair is independent.

The screen occupies the header mechanically even though those two signals are unused: use an appropriate breakout/stacking connector or carefully solder to the corresponding Pi-side pads. Do not confuse **BCM GPIO19** with **physical pin19**, which the display uses for touch SDA.

There is no need to disable touch for these pins. In particular, the installed `waveshare-touch-28dpi` overlay also creates the default-on GPIO18 backlight node; removing the whole overlay discards that backlight setup as well. If touch is ever disabled, preserve backlight configuration explicitly.

### Configuration and service access

The repository native unit sets these defaults before loading `/etc/pipclock.env`:

```ini
PIPCLOCK_BUTTON_PREV=19
PIPCLOCK_BUTTON_NEXT=26
```

These are **BCM numbers**, not header positions. Both variables must be set to distinct integer BCM pins in the range 0–27, or both must be unset/empty. An incomplete pair, invalid value, unavailable dependency, permission failure or busy GPIO is a clear startup error, not a silent fallback. A startup log identifies the configured pins; normal presses are not logged individually. GPIO resources are released at shutdown and on partial startup failure.

Ordinary desktop runs have neither variable set and do not import or require GPIO libraries. For a compatible Pi installation, provide the distro dependencies and service-account access:

```sh
sudo apt-get install --no-install-recommends python3-gpiozero python3-lgpio
```

The packages above **already existed on this Pi**; the command is for provisioning systems that lack them, not a record of a new installation here. The native unit supplies `SupplementaryGroups=video render input gpio` at service start, so a separate persistent `usermod` change is not needed for the systemd process. Install the updated unit, run `sudo systemctl daemon-reload`, then restart `pipclock.service` to apply service changes. No passwordless-sudo policy or touch/backlight overlay change is required.

To disable buttons while retaining the native display, use `sudoedit /etc/pipclock.env`, preserving the existing host/token settings and root-owned `0600` permissions, and add **both** empty overrides:

```ini
PIPCLOCK_BUTTON_PREV=
PIPCLOCK_BUTTON_NEXT=
```

Then run `sudo systemctl restart pipclock.service`. To re-enable the default wiring, remove both overrides or set them to `19` and `26`, respectively. Do not publish the rest of this secret environment file.

### Press behavior and verification boundaries

Each press enters logical idle immediately and moves one place backward/forward through the ordered [idle playlist](api.md#idle-playlist), wrapping at either end. While already idle, stepping uses the currently visible entry, including automatic rotations since the last rendered frame. If an explicit action is itself in the playlist, stepping uses that entry; otherwise (including the startup wave), next chooses the first entry and previous chooses the last. A one-entry playlist is valid.

Automatic rotation uses fixed 10:1 per-entry rarity: each selected normal action occurs ten times per cycle for each selected retro action's once. Buttons ignore those weights and walk the configured list once per entry; direct API actions are immediate too. Membership determines eligibility. The default group now has 11 entries (the previous nine plus `windows_bsod` and `windows_shutdown`); retro-only groups alternate equally and one-entry groups run continuously. Existing saved groups are not silently migrated: extend them through the [idle API](api.md#idle-playlist), preserving their other entries and interval. Configuration remains `actions` and `interval` only.

A press interrupts an explicit event/reaction, clears its reaction caption, and resets logical/pose time and the automatic-rotation timer. The selected pose then gets a full configured interval before automatic rotation. Independent timed messages keep their content, remaining lifetime, text size and scrolling clock; a still-active message hidden by a caption can become visible when the press clears that caption. A press never changes or saves playlist membership/order or interval. Explicit events/reactions, expiry back into idle and playlist updates reset the manual selection offset.

Live inspection before enabling the controller found GPIO19 and GPIO26 as inputs reading low; `/dev/gpiochip0` and `/dev/gpiomem` were `root:gpio`, mode `0660`. A staged real-LGPIO initialization subsequently claimed both inputs without root and observed both reading high. The controller requests internal pull-ups; the `--` field printed by `pinctrl` is not treated as an independent bias measurement. Neither probe establishes physical switch wiring or electrical debounce. Hardware-independent edge tests use gpiozero's injected `MockFactory`. Recheck ownership if other hardware/overlays are added.

## USB debugging and SSH access

The assistant added the early `dwc2,g_ether` load, peripheral overlay and the official cloud-init setting:

```yaml
rpi:
  enable_usb_gadget: true
```

The installed `rpi-usb-gadget-ics.service` is the distribution's USB Internet Connection Sharing auto-switcher (`/usr/libexec/rpi-usb-gadget/ics-watch`), using NetworkManager and `usb0`. The live interface has `10.12.194.1/28`; Wi-Fi remains the independently verified administration/API path.

USB **serial** was not enabled: no deployed `g_serial`, `g_multi`, `ttyGS0` console or serial-getty setup. Removing the GPIO UART console did not create a USB console. Historical macOS USB Ethernet tests saw `AppleUserECM` traffic stalling, consistent with [the upstream gadget issue](https://github.com/raspberrypi/rpi-usb-gadget/issues/27); no successful macOS-driver fix was installed. A temporary Mac address `10.12.194.2/28` used during diagnosis was reverted to DHCP.

### What the SD/SSH investigation actually established

The Imager/user configuration already supplied hostname `maclock`, account `lukasz`, Wi-Fi credentials, `ssh_pwauth: true` and `systemctl enable --now ssh`. These settings were preserved.

Read-only root-partition/cloud-init diagnostics showed that the reported connection refusal occurred at **2026-10-27 18:23:51 UTC**, just before cloud-init's SSH enablement after **18:23:54 UTC**. It was startup timing, not evidence of broken host keys or an account that needed resetting. The card was ejected **without an offline SSH configuration repair**: no password/account reset, cloud-init rerun/cache reset or cloud-init disablement was applied.

The user supplied the currently working `omp_tmp_raspbery` SSH identity. The earlier `ssh-copy-id` suggestion for `lci_01_prv_nix.pub` was an instruction, not an independently verified assistant key installation.

The Mac needed administrator access plus Full Disk Access for the parent terminal; Ghostty had to be restarted after granting it. `sudo` alone does not bypass macOS privacy controls. The SD device's permissions were not loosened. Root inspection used `debugfs` **without `-w`**. The historical `/dev/rdisk4s2` name is not stable—identify the current external card/partition before any future command.

For future **read-only** log extraction on an Apple Silicon Mac with Homebrew `e2fsprogs`, first identify the card:

```sh
diskutil list external physical
```

Run `sudo -v` separately and authenticate, then run this block and enter the confirmed raw root-partition path when prompted:

```sh
printf 'Confirmed raw SD root partition: '
IFS= read -r ROOT_DEVICE
OUT="$HOME/Library/Application Support/maclock-clawd/sd-backups/$(date +%Y%m%d-%H%M%S)-read-only-diagnostics"
(
  umask 077
  mkdir -p "$OUT"
  sudo /opt/homebrew/opt/e2fsprogs/sbin/debugfs \
    -R 'cat /var/log/cloud-init-output.log' "$ROOT_DEVICE" > "$OUT/cloud-init-output.log"
)
```

The output may contain provisioning details: keep it private and do not commit it. This recipe reads the filesystem; it does not perform a repair.

### Correct SSH command

Run the complete command in a normal Mac terminal:

```sh
ssh -i "$HOME/.ssh/omp_tmp_raspbery" lukasz@192.168.1.57
```

The key is an **argument to `ssh -i`**, not an executable. Do not run the key's path as a command or `chmod +x` it. Key-based SSH login and sudo are separate: the key avoids an SSH password prompt; administrative commands can still require the Pi account's password.

An earlier Ghostty multi-argument launcher attempted to execute the key path. It was replaced by an explicit SSH command launched through a temporary `.command` file in macOS Terminal. Those launchers were removed; they are not required for API use or normal administration. No new passwordless-sudo policy or root SSH login was introduced by the LAN/text deployments.

An **existing**, not assistant-created, `/etc/sudoers.d/010_global-tty` contains `Defaults timestamp_type=global`. Consequently a recent interactive authorization can allow another noninteractive sudo command, but an expired/missing ticket still fails. This is not a `NOPASSWD` grant, and the deployment did not change that policy.

## Locale configuration

The current system default is:

```ini
LANG=en_GB.UTF-8
```

Generated locales include `en_GB.utf8`, `en_US.utf8` and `pl_PL.utf8`, alongside `C`, `C.utf8` and `POSIX`. SSH from a Mac may forward `LC_CTYPE=en_US.UTF-8`, so a session can legitimately show that value while the system default remains British English.

The actual locale change was limited to backing up `/etc/locale.gen` as `/etc/locale.gen.maclock-backup`, uncommenting `en_US.UTF-8 UTF-8`, and retaining file mode `0644`. Existing British/Polish locales, `LANG=en_GB.UTF-8` and the Polish keyboard layout were **not newly configured**.

To inspect the effective settings without changing them:

```sh
localectl status
locale
locale -a
cat /etc/default/locale
```

After the reviewed `/etc/locale.gen` edit, the command actually used was:

```sh
sudo env LC_ALL=C locale-gen --keep-existing
```

Do not paper over an unavailable locale by exporting a permanent `LC_ALL`; generate the requested locale. The application's bundled DSEG clock font is independent of system locale. Unicode message glyphs still depend on installed fonts.

## Native service and black-screen fix

[deploy/pipclock.service](../deploy/pipclock.service) is the authoritative unit source. It runs `/usr/bin/python3 -m pipclock` from `/opt/maclock-clawd` as `pipclock`, with fullscreen output, port 8765 and application rotation 90.

Important integration settings:

- `PAMName=login`, `/dev/tty1`, `StandardInput=tty` and `Conflicts=getty@tty1.service` provide the console/session context and avoid a competing tty1 login console. There was no separate permanent getty mask.
- `SupplementaryGroups=video render input gpio` grants graphics/input and button GPIO access.
- `SDL_VIDEODRIVER=kmsdrm` selects native display output.
- **`SDL_FRAMEBUFFER_ACCELERATION=opengles2`** selects VC4's supported GLES2 framebuffer path.
- `StateDirectory=pipclock`, mode `0700`, provides persistent writable storage without making application source writable.
- `NoNewPrivileges=true`, `UMask=0077` and `Restart=on-failure` retain the service's restricted execution model.
- Native production does **not** enable `--preview`, so no JPEG encoding/browser process is needed on the Pi.

The black-panel fault was not simply an API failure: Python/pygame could draw a valid CPU-side scene while the DRM scanout buffer stayed black. SDL selected its desktop `opengl` framebuffer renderer although VC4 exposed an OpenGL ES context. Explicit `opengles2` fixed the normal pygame path; DRM framebuffer readback and a full reboot were exercised during that repair. A healthy `/health` alone is **not** proof that the physical panel is displaying pixels.

Do not reintroduce the rejected workarounds: `pygame.SCALED`, `LIBGL_ALWAYS_SOFTWARE=1` or a forced desktop OpenGL path. An experimental `SDL_RENDER_DRIVER=opengles2` demonstrated the cause, but the permanent setting is **`SDL_FRAMEBUFFER_ACCELERATION=opengles2`**. Temporary `/run/systemd/system/pipclock.service.d/presentation-diagnostic.conf`, diagnostic Python files, one-time `maclock-boot-proof.service` and boot/scanout helpers were removed after verification. They are not permanent services; `/run` proof files were volatile evidence.

### Application and artwork installed on the Pi

The current application catalog has **64 actions**. Normal scenes use terracotta Clawd on sand with enlarged lower-positioned artwork and an hours/minutes-only clock, without the old footer/date/slogans. The two user-provided retro Windows backgrounds instead fill the screen and omit the clock and normal body/footer; the Wi-Fi badge and API text remain available. `windows_bsod` and `windows_shutdown` are visual-only effects, never a real crash, restart or shutdown. Each defaults to 20 seconds and has one peek starting at 3 seconds and ending at 8 seconds; shorter-than-3-second triggers expire before the peek. See the [duration-20 API examples](api.md#retro-windows-scenes) and the [artwork credits](artwork.md).

`pipclock/assets/fonts/DSEG7Classic-Regular.ttf` and its OFL license are bundled application assets. DSEG was **not** installed as a global system font. Artwork sources and font licensing are documented in [artwork and attribution](artwork.md).

## LAN authentication and persistent idle

The repository unit defaults to loopback. The installed device overrides it through private `/etc/pipclock.env`:

- `PIPCLOCK_HOST=0.0.0.0` — listen on the Pi's interfaces, even before Wi-Fi receives its address.
- `PIPCLOCK_TOKEN` — the randomly generated shared bearer secret; its value is intentionally not documented.

The matching secret was generated on the Mac using `secrets.token_hex(32)` and written to private client/staging files before secure transfer and root installation. No actual token value is included in the repository. No Nginx/proxy, TLS termination, firewall changes or router port forwarding were added; requests go directly to the application's HTTP server.

For an **existing** device, edit that file with `sudoedit`, preserving the token and other settings, keep it root-owned mode `0600`, and restart the service. Do not rotate the token accidentally by generating a new client-only value.

The service unit also sets `PIPCLOCK_IDLE_CONFIG=/var/lib/pipclock/idle.json`. The app saves validated playlist updates atomically with mode `0600`. Only playlist membership/order and interval persist; live events, messages, captions and playlist position do not. Use the [idle API examples](api.md#idle-playlist), not manual editing, for normal changes.

The corresponding Mac token file is:

```text
~/Library/Application Support/maclock-clawd/api.env
```

It is mode `0600`. API callers source/export its variable as shown in the [cookbook](api.md#client-setup-on-this-mac). Neither secret file belongs in Git, screenshots, logs or bug reports. HTTP bearer authentication does not encrypt messages or tokens: use only a trusted LAN, never forward port 8765 from the Internet, and use an encrypted tunnel for untrusted networks.

## Deploying and updating

### Existing device-specific updater

The current GPIO/retro stage at `/home/lukasz/maclock-buttons.JqhvOL` contains credential-free `release.tar.gz`, `release.sha256` and `install.sh`. This updater:

1. Requires root and verifies the archive checksum.
2. Checks the existing `pipclock` account, private `/etc/pipclock.env` and installed GPIO imports before stopping anything.
3. Copies the existing source and installed service unit into `/opt/maclock-clawd.before-redesign.XXXXXX`.
4. Stops the service and extracts the release under `/opt/maclock-clawd`, without modifying the token file or persistent state directory.
5. Installs the repository unit, reloads systemd and enables/starts the service with its runtime `gpio` group and GPIO19/GPIO26 defaults.
6. Waits for native health and prints service state, pin configuration and the backup path. LAN authorization and rendered pixels are checked separately; health is not display proof.

The older `/home/lukasz/maclock-redesign.RFLoD6` stage belongs to the earlier LAN/text deployment and includes private `lan.env`; it is not the current release.

From the Mac, this one-time administration command is:

```sh
ssh -t -i "$HOME/.ssh/omp_tmp_raspbery" lukasz@192.168.1.57 \
  'sudo sh /home/lukasz/maclock-buttons.JqhvOL/install.sh'
```

Enter the **Pi account password** if sudo asks, directly in that terminal. Do not paste it into chat. A passwordless SSH key does not grant passwordless sudo. This staging directory is a retained device-specific artifact, not a universally installed command; do not assume it exists on another Pi or contains a later Git checkout.

### Reproducible source update from the repository

On the Mac, commit the intended release first. From the repository root, prepare a credential-free archive of **committed HEAD only** and a fresh remote stage. `git archive` omits working-tree secrets, caches and macOS extended attributes; uncommitted changes are deliberately not deployed:

```sh
(
set -e
PI=lukasz@192.168.1.57
KEY="$HOME/.ssh/omp_tmp_raspbery"
LOCAL_RELEASE=$(mktemp -d)
trap 'rm -rf "$LOCAL_RELEASE"' EXIT
git archive --format=tar.gz --output="$LOCAL_RELEASE/release.tar.gz" HEAD
(
  cd "$LOCAL_RELEASE"
  shasum -a 256 release.tar.gz > release.sha256
)
REMOTE_RELEASE=$(ssh -i "$KEY" "$PI" 'mktemp -d /home/lukasz/maclock-release.XXXXXX')
scp -i "$KEY" "$LOCAL_RELEASE/release.tar.gz" "$LOCAL_RELEASE/release.sha256" "$PI:$REMOTE_RELEASE/"
ssh -t -i "$KEY" "$PI" "cd '$REMOTE_RELEASE' && exec /bin/bash -i"
)
```

You are now in the new release directory **on the Pi**. Run `sudo -v` separately and enter the password before pasting the next block; do not feed a script heredoc into an SSH tty while sudo is waiting for a password.

```sh
sha256sum -c release.sha256 &&
BACKUP=$(sudo mktemp -d /opt/maclock-clawd.before-redesign.XXXXXX) &&
sudo cp -a /opt/maclock-clawd/. "$BACKUP/" &&
sudo systemctl stop pipclock.service &&
sudo tar --no-same-owner -xzf release.tar.gz -C /opt/maclock-clawd &&
sudo install -m 0644 /opt/maclock-clawd/deploy/pipclock.service /etc/systemd/system/pipclock.service &&
sudo systemctl daemon-reload &&
sudo systemctl enable --now pipclock.service &&
printf 'Previous source: %s\n' "$BACKUP"
```

This preserves the existing token and idle settings outside the application tree. It assumes the already-provisioned service account, dependencies and environment. On a new image, provision those and the hardware first. Do not archive `.ssh`, private environment files, SD backups or cloud-init user-data.

This GPIO update uses the already-installed `python3-gpiozero` and `python3-lgpio` packages. It adds `gpio` only to the service's `SupplementaryGroups`, not to the account's permanent group membership. No display/touch overlay, backlight setting, network profile, locale, sudo policy or token rotation is required. After updating an existing installation, append missing `windows_bsod` and `windows_shutdown` entries through the idle API, preserving the existing entries/order and interval; the updater itself never rewrites the saved group.

## Health checks and troubleshooting

On the Pi:

```sh
systemctl is-active pipclock.service
systemctl is-enabled pipclock.service
systemctl show pipclock.service -p MainPID -p NRestarts -p StateDirectory
systemctl cat pipclock.service
journalctl -u pipclock.service -n 80 --no-pager
ss -ltn
```

From the Mac, use the [authenticated API cookbook](api.md#health-and-current-snapshot). A public health check is:

```sh
curl -q --silent --show-error --fail-with-body http://192.168.1.57:8765/health
```

| Symptom | Meaning / next check |
| --- | --- |
| `curl: (7) Failed to connect` | TCP did not reach the API; inspect service state, IP and listener before changing tokens. `127.0.0.1:8765` is local-only; the deployed LAN listener is `0.0.0.0:8765`. |
| HTTP `401` | The API is reachable; source the correct client token and send the bearer header. |
| HTTP `404` on `/` or `/frame.jpg` | Expected for native production: preview is not enabled. |
| `sudo: a password is required` | Administrative authorization is missing; run the interactive SSH command, not repeated noninteractive retries. |
| Healthy API, lit but black panel | Inspect the native unit, tty/session/device permissions and especially `SDL_FRAMEBUFFER_ACCELERATION=opengles2`; health is not scanout verification. |
| Idle-setting POST returns `500` | Persistence failed; inspect the private state directory/permissions and service journal. The old configuration remains active. |
| Process fails after a manually edited idle file | Invalid stored JSON/settings intentionally fail startup; restore a valid saved configuration rather than suppressing the error. |

Do not dump `/etc/pipclock.env`, `/proc/PID/environ`, authorized keys, Wi-Fi profiles or cloud-init user-data into public diagnostics. If a full reboot is planned, retain console/SD recovery access: reboot testing was performed for the GLES2 repair, but it is not a reason to reboot a working unit during documentation-only work.

## Backups and rollback

Before SD edits, private boot-file snapshots were made on the Mac:

```text
~/Library/Application Support/maclock-clawd/sd-backups/20261027-190017/
~/Library/Application Support/maclock-clawd/sd-backups/20261027-204841-ssh-repair/
```

They contain `config.txt`, `cmdline.txt`, `user-data`, `network-config`, `meta-data` and `issue.txt`. These are **private**: some contain provisioning credentials. A directory named `ssh-repair` is not itself proof that a repair succeeded. Keep paths containing `Application Support` quoted on one physical line; a newline inside quotes becomes part of the filename.

Additional read-only SSH/cloud-init diagnostics were retained privately at `~/maclock-pi-diagnostics-9pbtj_pr`. They are not release inputs and must not be copied into Git.

On the Pi, source snapshots are in `/opt/maclock-clawd.before-redesign.*`. To inspect available snapshot directories without printing credentials:

```sh
sudo find /opt -maxdepth 1 -type d -name 'maclock-clawd.before-redesign.*' -print
```

Rollback is an administrative operation, not performed as part of this documentation update. Stop the service; preserve the currently installed source in a separate directory; restore a deliberately chosen snapshot to `/opt/maclock-clawd`; then restart and verify the API **and** display. Preserve `/etc/pipclock.env` and `/var/lib/pipclock` separately. Do not blindly reinstall an older unit that predates the GLES2 fix or LAN settings. Old application snapshots can lack `text_size` or `/api/idle`; inspect API compatibility before rolling back.

## Verification boundaries

The display/USB overlays were validated with Raspberry Pi firmware-aware `dtmerge`/`dtapply` from [raspberrypi/utils](https://github.com/raspberrypi/utils/tree/b8961eb9a689a3c0465db108176d0ee425379730) against the Zero W device tree; a generic `fdtoverlay` trial failed with `FDT_ERR_NOTFOUND` and was replaced by that validation, not by patched blobs. The original black-scanout repair included DRM/GBM readback and a complete Pi reboot. Physical touch-axis accuracy and a reliable Mac USB-Ethernet fix were not claimed.

For application release `148fd10`, 61 behavior/rendering tests passed, the actual browser mirror showed large text and right-to-left scrolling, and the real Pi test process restored an idle playlist after a cold process restart. Production API checks exercised 80/96 px text, atomic rejection of invalid size 97, caption expiry and a 5-second pool-to-reading rotation; the default 30-second playlist was restored and saved afterward. The systemd service was active/enabled with no automatic restarts. These are historical verification results, not a substitute for checking a device after future OS, display or application changes.

## Release landmarks

| Commit | Recorded outcome |
| --- | --- |
| `5c3f102` | Initial native KMS deployment with application-level panel rotation |
| `35801a3` | Display redesign and published permanent GLES2 unit fix |
| `ed76a09` | Bundled approved DSEG calculator-clock font and license |
| `e296219` | Configurable, bearer-authenticated native LAN API |
| `148fd10` | Large scrolling text and configurable persistent idle playlist |

The final idle/text release was tested through production API calls and a separate Pi process cold restart; no second full-system reboot after that release is claimed. Rollback instructions are operational guidance, not a claim that a rollback was executed.
