class EarlbearPlugins < Formula
  desc "EarlBear Claude plugin marketplace - installs all earlbear Claude skills"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
  license "MIT"

  def install
    libexec.install "scripts/install-plugins.sh"
    (libexec/"marketplace").install Dir["plugins-bundle/*"]
    (libexec/"marketplace/.claude-plugin").install Dir["plugins-bundle/.claude-plugin/*"]
  end

  def post_install
    if which("claude")
      system "bash", libexec/"install-plugins.sh", libexec/"marketplace"
    else
      opoo "claude CLI not found. After installing Claude Code, run:\n  " \
           "bash #{libexec}/install-plugins.sh #{libexec}/marketplace"
    end
  end

  test do
    assert_predicate libexec/"install-plugins.sh", :executable?
  end
end
