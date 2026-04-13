class Ebdocs < Formula
  desc "EarlBear Google Docs CLI - Docker-wrapped ebdocs"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebdocs").install Dir["src/ebdocs/*"]
    (libexec/"ebdocs").install "wrappers/ebdocs/wrapper.sh"
    bin.install_symlink libexec/"ebdocs/wrapper.sh" => "ebdocs"
  end

  def post_install
    if which("docker")
      system "docker", "build", "-t", "ebdocs", "-q", libexec/"ebdocs"
    else
      opoo "docker not found - run `docker build -t ebdocs #{libexec}/ebdocs` after installing Docker"
    end
  end

  test do
    assert_predicate bin/"ebdocs", :executable?
    output = shell_output("#{bin}/ebdocs doc list 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
