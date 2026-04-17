class Ebdocs < Formula
  desc "EarlBear Google Docs CLI - Docker-wrapped ebdocs"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "git@github.com:EarlBear/homebrew-tap.git",
      tag:      "v1.1.0",
      revision: "440f07b66f77578225da9f553b2e00488eaaa2cb"
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
