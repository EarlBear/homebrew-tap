class AgentCli < Formula
  desc "EarlBear cloud agent admin CLI - wraps ebjira with agent-specific commands"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "https://github.com/EarlBear/homebrew-tap/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "58d34db85c4ebb48cb12ea70ec1f1ea864d7d026e91ce6085bb8ec81628b657d"
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
