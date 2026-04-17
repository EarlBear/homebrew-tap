class EarlbearPlugins < Formula
  desc "EarlBear Claude plugin marketplace - installs all earlbear Claude skills"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "git@github.com:EarlBear/homebrew-tap.git",
      tag:      "v1.1.0",
      revision: "440f07b66f77578225da9f553b2e00488eaaa2cb"
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
