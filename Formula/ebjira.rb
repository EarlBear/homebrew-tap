class Ebjira < Formula
  desc "EarlBear Jira CLI - Docker-wrapped ebjira"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "git@github.com:EarlBear/homebrew-tap.git",
      tag:      "v1.1.0",
      revision: "440f07b66f77578225da9f553b2e00488eaaa2cb"
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
