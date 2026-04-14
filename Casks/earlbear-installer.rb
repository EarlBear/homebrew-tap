cask "earlbear-installer" do
  version "1.0.0"
  sha256 "cbfe28cc84aaa1e624ae15bf55597f6b8718bf998fee7e46bea6ac1db243bce2"

  url "https://github.com/EarlBear/apps/releases/download/installer-v#{version}/EarlBear-Installer-#{version}.dmg"
  name "EarlBear Installer"
  desc "One-click setup wizard for EarlBear developer tooling on macOS"
  homepage "https://github.com/EarlBear/apps"

  # Minimum macOS 12 (Monterey) — enforced in install.sh too
  depends_on macos: ">= :monterey"

  app "EarlBear Installer.app"

  # Remove app and any generated logs
  zap trash: [
    "~/Library/Logs/EarlBear",
    "~/.config/earlbear",
  ]
end
