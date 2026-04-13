class Ebshop < Formula
  desc "EarlBear Shopify CLI - Docker-wrapped ebshop"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebshop").install Dir["src/ebshop/*"]
    (libexec/"ebshop").install "wrappers/ebshop/wrapper.sh"
    bin.install_symlink libexec/"ebshop/wrapper.sh" => "ebshop"
  end

  def post_install
    if which("docker")
      system "docker", "build", "-t", "ebshop", "-q", libexec/"ebshop"
    else
      opoo "docker not found - run `docker build -t ebshop #{libexec}/ebshop` after installing Docker"
    end
  end

  test do
    assert_predicate bin/"ebshop", :executable?
    output = shell_output("#{bin}/ebshop shop info 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
