class AgentCli < Formula
  desc "EarlBear cloud agent admin CLI - wraps ebjira with agent-specific commands"
  homepage "https://github.com/bytesofpurpose/homebrew-earlbear"
  url "https://github.com/bytesofpurpose/homebrew-earlbear/archive/refs/tags/v1.0.0.tar.gz"
  sha256 "0019dfc4b32d63c1392aa264aed2253c1e0c2fb09216f8e2cc269bbfb8bb49b5"
  license "MIT"

  depends_on "bytesofpurpose/earlbear/ebjira"

  def install
    bin.install "src/agent-cli/agent-cli.sh" => "agent-cli"
  end

  test do
    assert_predicate bin/"agent-cli", :executable?
    assert_match "agent-cli", shell_output("#{bin}/agent-cli help 2>&1")
  end
end
