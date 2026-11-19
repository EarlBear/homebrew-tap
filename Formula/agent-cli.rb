class AgentCli < Formula
  desc "EarlBear cloud agent admin CLI - wraps ebjira with agent-specific commands"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.2.0.tar.gz"
  sha256 "1613bb363d5106328b1837dc6eced11020200b93474baa0015972e99e78d1a74"
  license "MIT"

  depends_on "earlbear/tap/ebjira"

  def install
    bin.install "src/agent-cli/agent-cli.sh" => "agent-cli"
  end

  test do
    assert_predicate bin/"agent-cli", :executable?
    assert_match "agent-cli", shell_output("#{bin}/agent-cli help 2>&1")
  end
end
