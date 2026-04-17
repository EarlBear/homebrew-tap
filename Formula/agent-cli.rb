class AgentCli < Formula
  desc "EarlBear cloud agent admin CLI - wraps ebjira with agent-specific commands"
  homepage "https://github.com/EarlBear/homebrew-tap"
  url "git@github.com:EarlBear/homebrew-tap.git",
      tag:      "v1.1.0",
      revision: "440f07b66f77578225da9f553b2e00488eaaa2cb"
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
