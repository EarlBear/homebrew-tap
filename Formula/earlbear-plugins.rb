class EarlbearPlugins < Formula
  desc "EarlBear Claude plugins, installed from the EarlBear GitHub marketplace"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
  license "MIT"

  # The plugins are not copied into this formula. install-plugins.sh adds the
  # private GitHub marketplace EarlBear/marketplace-claude-plugins and installs
  # the plugins from it, so they are always the current ones.
  def install
    libexec.install "scripts/install-plugins.sh"
  end

  def post_install
    if which("claude")
      system "bash", libexec/"install-plugins.sh"
    else
      opoo "claude CLI not found. After installing Claude Code, run:\n  " \
           "bash #{opt_libexec}/install-plugins.sh"
    end
  end

  def caveats
    <<~EOS
      The plugins come from the private GitHub repo EarlBear/marketplace-claude-plugins,
      so this Mac needs GitHub access to EarlBear (an SSH key for github.com).
      To install or update them again later, run:
        bash #{opt_libexec}/install-plugins.sh
    EOS
  end

  test do
    assert_predicate libexec/"install-plugins.sh", :executable?
  end
end
