class Ebjira < Formula
  desc "EarlBear Jira CLI - Docker-wrapped ebjira"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
  license "MIT"

  depends_on "docker"

  def install
    (libexec/"ebjira").install Dir["src/ebjira/*"]
    (libexec/"ebjira").install "wrappers/ebjira/wrapper.sh"
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
