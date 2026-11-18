class Ebjira < Formula
  desc "EarlBear Jira CLI - Docker-wrapped ebjira"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "1613bb363d5106328b1837dc6eced11020200b93474baa0015972e99e78d1a74"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebjira").install Dir["src/ebjira/*"]
    (libexec/"ebjira").install "wrappers/ebjira/wrapper.sh"
    bin.install_symlink libexec/"ebjira/wrapper.sh" => "ebjira"
  end

  # No post_install: Homebrew runs it in a sandbox that cannot reach Docker, so
  # the wrapper builds the image itself on first run.
  def caveats
    <<~EOS
      The first ebjira command builds its Docker image (Docker must be running).
      After an upgrade, rebuild the image so it picks up the new version:
        docker build -t ebjira #{opt_libexec}/ebjira
    EOS
  end

  test do
    assert_predicate bin/"ebjira", :executable?
    output = shell_output("#{bin}/ebjira issue list 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
