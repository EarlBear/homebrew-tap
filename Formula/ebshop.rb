class Ebshop < Formula
  desc "EarlBear Shopify CLI - Docker-wrapped ebshop"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "git@github.com:EarlBear/homebrew-tap.git",
      tag:      "v1.1.0",
      revision: "440f07b66f77578225da9f553b2e00488eaaa2cb"
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
