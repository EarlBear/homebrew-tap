class EarlbearPlugins < Formula
  desc "EarlBear Claude plugin marketplace - installs all earlbear Claude skills"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
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
