class Earlbear < Formula
  desc "EarlBear — install all CLI tools and Claude plugins in one command"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"
  version "1.0.0"

  bottle :unneeded

  depends_on "bytesofpurpose/earlbear/ebjira"
  depends_on "bytesofpurpose/earlbear/ebdocs"
  depends_on "bytesofpurpose/earlbear/ebshop"
  depends_on "bytesofpurpose/earlbear/ebdeck"
  depends_on "bytesofpurpose/earlbear/agent-cli"
  depends_on "bytesofpurpose/earlbear/earlbear-plugins"

  def install
    bin.install "scripts/setup-env.sh" => "earlbear-setup"
    # Install .env.example to share/earlbear
    (share/"earlbear").install "scripts/env.example" => ".env.example"
  end

  def caveats
    <<~EOS
      EarlBear CLIs are installed. Configure credentials:

        earlbear-setup

      Or manually:
        mkdir -p ~/.config/earlbear
        cp #{share}/earlbear/.env.example ~/.config/earlbear/.env
        # Edit ~/.config/earlbear/.env with your credentials

      All CLIs read from: ~/.config/earlbear/.env
      Override location:  export EARLBEAR_CONFIG_DIR=/path/to/config
    EOS
  end

  test do
    assert_predicate bin/"earlbear-setup", :executable?
  end
end
