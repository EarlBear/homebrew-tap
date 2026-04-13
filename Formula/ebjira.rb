class Ebjira < Formula
  desc "EarlBear Jira CLI - Docker-wrapped ebjira"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebjira").install Dir["src/ebjira/*"]
    bin.install_symlink libexec/"ebjira/wrapper.sh" => "ebjira"
  end

  def post_install
    if which("docker")
      system "docker", "build", "-t", "ebjira", "-q", libexec/"ebjira"
    else
      opoo "docker not found - run `docker build -t ebjira #{libexec}/ebjira` after installing Docker"
    end
  end

  test do
    assert_predicate bin/"ebjira", :executable?
    output = shell_output("#{bin}/ebjira issue list 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
