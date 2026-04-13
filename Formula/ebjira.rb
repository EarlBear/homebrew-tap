class Ebjira < Formula
  desc "EarlBear Jira CLI — Docker-wrapped ebjira"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  license "MIT"
  version "1.0.0"

  bottle :unneeded

  depends_on "docker"

  def install
    # Bundle Dockerfile + Python source so image can be built post-install
    (libexec/"ebjira").install Dir["src/ebjira/*"]
    # Install adapted wrapper script
    (libexec/"ebjira").install "src/ebjira/wrapper.sh"
    bin.install_symlink libexec/"ebjira/wrapper.sh" => "ebjira"
  end

  def post_install
    if which("docker")
      system "docker", "build", "-t", "ebjira", "-q", libexec/"ebjira"
    else
      opoo "docker not found — run `docker build -t ebjira #{libexec}/ebjira` after installing Docker"
    end
  end

  test do
    assert_predicate bin/"ebjira", :executable?
    # Expects CONFIG_MISSING error (no .env), not a crash
    output = shell_output("#{bin}/ebjira issue list 2>&1", 2)
    assert_match "CONFIG_MISSING", output
  end
end
