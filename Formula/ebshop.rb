class Ebshop < Formula
  desc "EarlBear Shopify CLI - Docker-wrapped ebshop"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebshop").install Dir["src/ebshop/*"]
    (libexec/"ebshop").install "wrappers/ebshop/wrapper.sh"
    bin.install_symlink libexec/"ebshop/wrapper.sh" => "ebshop"
  end

  # No post_install: Homebrew runs it in a sandbox that cannot reach Docker, so
  # the wrapper builds the image itself on first run.
  def caveats
    <<~EOS
      The first ebshop command builds its Docker image (Docker must be running).
      After an upgrade, rebuild the image so it picks up the new version:
        docker build -t ebshop #{opt_libexec}/ebshop
    EOS
  end

  test do
    assert_predicate bin/"ebshop", :executable?
    output = shell_output("#{bin}/ebshop shop info 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
