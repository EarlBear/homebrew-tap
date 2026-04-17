class Earlbear < Formula
  desc "Install all EarlBear CLI tools and Claude plugins in one command"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
  license "MIT"

  depends_on "git-lfs"
  depends_on "gh"
  depends_on "earlbear/tap/agent-cli"
  depends_on "earlbear/tap/earlbear-plugins"
  depends_on "earlbear/tap/ebdeck"
  depends_on "earlbear/tap/ebdocs"
  depends_on "earlbear/tap/ebjira"
  depends_on "earlbear/tap/ebshop"

  def install
    bin.install "scripts/setup-env.sh" => "earlbear-setup"
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
