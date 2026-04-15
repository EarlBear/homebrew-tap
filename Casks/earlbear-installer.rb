cask "earlbear-installer" do
  version "1.1.0"
  sha256 "6e10f8c1f28faa1e805895079ef49ec1da28225c33d858845e658e2935378d62"

  url "https://github.com/EarlBear/apps/releases/download/installer-v#{version}/EarlBear-Installer-#{version}.dmg"
  name "EarlBear Installer"
  desc "One-click setup wizard for EarlBear developer tooling on macOS"
  homepage "https://github.com/EarlBear/apps"

  # Minimum macOS 12 (Monterey) — enforced in install.sh too
  depends_on macos: ">= :monterey"

  app "EarlBear Installer.app"

  # Strip Gatekeeper quarantine flag so macOS doesn't show "unidentified developer" warning.
  # This is safe for internal team tooling; notarization (Apple Dev account) not required.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-d", "-r", "com.apple.quarantine",
                          "#{appdir}/EarlBear Installer.app"],
                   sudo: false
  end

  # Remove app and any generated logs
  zap trash: [
    "~/Library/Logs/EarlBear",
    "~/.config/earlbear",
  ]
end
