class EarlbearPlugins < Formula
  desc "EarlBear Claude plugins, installed from the EarlBear GitHub marketplace"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "1613bb363d5106328b1837dc6eced11020200b93474baa0015972e99e78d1a74"
  license "MIT"

  # The plugins are not copied into this formula. install-plugins.sh adds the
  # private GitHub marketplace EarlBear/marketplace-claude-plugins and installs
  # the plugins from it, so they are always the current ones.
  def install
    libexec.install "scripts/install-plugins.sh"
  end

  # No post_install: Homebrew runs it in a sandbox that cannot read or write
  # ~/.claude or use your GitHub keys, so the plugins cannot be installed from
  # it. The caveats tell you to run the script yourself.
  def caveats
    <<~EOS
      This installs the plugin installer, not the plugins. To install the plugins
      (and later, to update them), run:
        bash #{opt_libexec}/install-plugins.sh
      It needs Claude Code (the claude command) and GitHub access to the private
      repo EarlBear/marketplace-claude-plugins: an SSH key for github.com, or
      HTTPS through gh (gh auth login, then gh auth setup-git).
    EOS
  end

  test do
    assert_predicate libexec/"install-plugins.sh", :executable?
  end
end
