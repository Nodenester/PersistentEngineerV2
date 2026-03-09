using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Threading.Tasks;
using StreamJsonRpc;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace GitPublisher;

public class McpServer
{
    private readonly string _workingDir;
    private readonly string? _githubToken;
    private readonly HttpClient _httpClient;

    public McpServer()
    {
        _workingDir = Environment.GetEnvironmentVariable("GIT_WORKING_DIR")
            ?? Environment.GetEnvironmentVariable("PROJECT_ROOT")
            ?? "/workspace/repo";
        _githubToken = Environment.GetEnvironmentVariable("GITHUB_TOKEN")
            ?? Environment.GetEnvironmentVariable("GIT_TOKEN");

        // Set up HTTP client for GitHub API
        _httpClient = new HttpClient();
        _httpClient.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("GitPublisher", "1.0"));
        _httpClient.DefaultRequestHeaders.Accept.Add(new MediaTypeWithQualityHeaderValue("application/vnd.github+json"));
        if (!string.IsNullOrEmpty(_githubToken))
        {
            _httpClient.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", _githubToken);
        }

        Console.Error.WriteLine($"[GitPublisher] Working directory: {_workingDir}");
        Console.Error.WriteLine($"[GitPublisher] GitHub token: {(_githubToken != null ? "configured" : "not set")}");
    }

    private (int exitCode, string stdout, string stderr) RunGit(string arguments, string? workDir = null)
    {
        var psi = new ProcessStartInfo
        {
            FileName = "git",
            Arguments = arguments,
            WorkingDirectory = workDir ?? _workingDir,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true
        };

        // Set up git credential if token is available
        if (!string.IsNullOrEmpty(_githubToken))
        {
            psi.EnvironmentVariables["GIT_ASKPASS"] = "echo";
            psi.EnvironmentVariables["GIT_TERMINAL_PROMPT"] = "0";
        }

        using var process = Process.Start(psi);
        if (process == null)
        {
            return (-1, "", "Failed to start git process");
        }

        var stdout = process.StandardOutput.ReadToEnd();
        var stderr = process.StandardError.ReadToEnd();
        process.WaitForExit();

        return (process.ExitCode, stdout, stderr);
    }

    [JsonRpcMethod("initialize")]
    public object Initialize(JToken? clientInfo = null, JToken? protocolVersion = null, JToken? capabilities = null)
    {
        Console.Error.WriteLine("[GitPublisher] Initialize called");
        return new
        {
            protocolVersion = "2024-11-05",
            capabilities = new
            {
                tools = new { listChanged = false }
            },
            serverInfo = new
            {
                name = "git-publisher",
                version = "1.0.0"
            }
        };
    }

    [JsonRpcMethod("notifications/initialized")]
    public void Initialized()
    {
        Console.Error.WriteLine("[GitPublisher] Initialized notification received");
    }

    [JsonRpcMethod("ping")]
    public object Ping() => new { };

    [JsonRpcMethod("tools/list")]
    public object ToolsList()
    {
        var tools = new List<object>
        {
            new
            {
                name = "git_status",
                description = "Get the current git status. Shows staged, unstaged, and untracked files.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["short"] = new { type = "boolean", description = "Use short format output (default: false)" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_add",
                description = "Stage files for commit. Use path='.' or path='-A' to stage all changes.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["path"] = new { type = "string", description = "File path to stage, or '.' for all, or '-A' for all including deletions" }
                    },
                    required = new[] { "path" }
                }
            },
            new
            {
                name = "git_commit",
                description = "Create a commit with the staged changes.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["message"] = new { type = "string", description = "Commit message" },
                        ["author"] = new { type = "string", description = "Author in format 'Name <email>' (optional)" }
                    },
                    required = new[] { "message" }
                }
            },
            new
            {
                name = "git_push",
                description = "Push commits to remote repository. Uses GITHUB_TOKEN for authentication.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["remote"] = new { type = "string", description = "Remote name (default: origin)" },
                        ["branch"] = new { type = "string", description = "Branch name (default: current branch)" },
                        ["set_upstream"] = new { type = "boolean", description = "Set upstream tracking (-u flag)" },
                        ["force"] = new { type = "boolean", description = "Force push (use with caution!)" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_pull",
                description = "Pull changes from remote repository.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["remote"] = new { type = "string", description = "Remote name (default: origin)" },
                        ["branch"] = new { type = "string", description = "Branch name (default: current branch)" },
                        ["rebase"] = new { type = "boolean", description = "Rebase instead of merge" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_branch",
                description = "List, create, or switch branches.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["action"] = new { type = "string", description = "Action: list, create, switch, delete" },
                        ["name"] = new { type = "string", description = "Branch name (required for create/switch/delete)" },
                        ["all"] = new { type = "boolean", description = "Show remote branches too (for list action)" }
                    },
                    required = new[] { "action" }
                }
            },
            new
            {
                name = "git_log",
                description = "View commit history.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["count"] = new { type = "integer", description = "Number of commits to show (default: 10)" },
                        ["oneline"] = new { type = "boolean", description = "Use one-line format (default: true)" },
                        ["all"] = new { type = "boolean", description = "Show all branches" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_diff",
                description = "Show changes between commits, working tree, etc.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["staged"] = new { type = "boolean", description = "Show staged changes (--cached)" },
                        ["path"] = new { type = "string", description = "Limit diff to specific path" },
                        ["stat"] = new { type = "boolean", description = "Show diffstat instead of full diff" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_reset",
                description = "Reset current HEAD to specified state.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["mode"] = new { type = "string", description = "Reset mode: soft, mixed, hard (default: mixed)" },
                        ["target"] = new { type = "string", description = "Commit or ref to reset to (default: HEAD)" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "git_stash",
                description = "Stash changes in working directory.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["action"] = new { type = "string", description = "Action: push, pop, list, drop, apply (default: push)" },
                        ["message"] = new { type = "string", description = "Stash message (for push action)" }
                    },
                    required = Array.Empty<string>()
                }
            },
            // GitHub Issue Tools
            new
            {
                name = "github_create_issue",
                description = "Create a new GitHub issue in the repository. Requires GITHUB_TOKEN with repo scope.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["owner"] = new { type = "string", description = "Repository owner (username or org). If not provided, extracted from git remote." },
                        ["repo"] = new { type = "string", description = "Repository name. If not provided, extracted from git remote." },
                        ["title"] = new { type = "string", description = "Issue title (required)" },
                        ["body"] = new { type = "string", description = "Issue body/description (supports markdown)" },
                        ["labels"] = new { type = "array", items = new { type = "string" }, description = "Array of label names to add" },
                        ["assignees"] = new { type = "array", items = new { type = "string" }, description = "Array of usernames to assign" }
                    },
                    required = new[] { "title" }
                }
            },
            new
            {
                name = "github_list_issues",
                description = "List issues in a GitHub repository.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["owner"] = new { type = "string", description = "Repository owner. If not provided, extracted from git remote." },
                        ["repo"] = new { type = "string", description = "Repository name. If not provided, extracted from git remote." },
                        ["state"] = new { type = "string", description = "Filter by state: open, closed, all (default: open)" },
                        ["labels"] = new { type = "string", description = "Comma-separated list of label names to filter by" },
                        ["per_page"] = new { type = "integer", description = "Results per page (default: 10, max: 100)" }
                    },
                    required = Array.Empty<string>()
                }
            },
            new
            {
                name = "github_get_issue",
                description = "Get details of a specific GitHub issue.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["owner"] = new { type = "string", description = "Repository owner. If not provided, extracted from git remote." },
                        ["repo"] = new { type = "string", description = "Repository name. If not provided, extracted from git remote." },
                        ["issue_number"] = new { type = "integer", description = "Issue number (required)" }
                    },
                    required = new[] { "issue_number" }
                }
            },
            new
            {
                name = "github_update_issue",
                description = "Update an existing GitHub issue.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["owner"] = new { type = "string", description = "Repository owner. If not provided, extracted from git remote." },
                        ["repo"] = new { type = "string", description = "Repository name. If not provided, extracted from git remote." },
                        ["issue_number"] = new { type = "integer", description = "Issue number (required)" },
                        ["title"] = new { type = "string", description = "New issue title" },
                        ["body"] = new { type = "string", description = "New issue body" },
                        ["state"] = new { type = "string", description = "State: open or closed" },
                        ["labels"] = new { type = "array", items = new { type = "string" }, description = "Replace labels with these" }
                    },
                    required = new[] { "issue_number" }
                }
            },
            new
            {
                name = "github_add_comment",
                description = "Add a comment to a GitHub issue or pull request.",
                inputSchema = new
                {
                    type = "object",
                    properties = new Dictionary<string, object>
                    {
                        ["owner"] = new { type = "string", description = "Repository owner. If not provided, extracted from git remote." },
                        ["repo"] = new { type = "string", description = "Repository name. If not provided, extracted from git remote." },
                        ["issue_number"] = new { type = "integer", description = "Issue or PR number (required)" },
                        ["body"] = new { type = "string", description = "Comment body (required, supports markdown)" }
                    },
                    required = new[] { "issue_number", "body" }
                }
            }
        };

        return new { tools };
    }

    [JsonRpcMethod("tools/call")]
    public object ToolsCall(string name, JToken arguments, JToken? _meta = null)
    {
        try
        {
            Console.Error.WriteLine($"[GitPublisher] Tool call: {name}");
            return name switch
            {
                "git_status" => GitStatus(arguments),
                "git_add" => GitAdd(arguments),
                "git_commit" => GitCommit(arguments),
                "git_push" => GitPush(arguments),
                "git_pull" => GitPull(arguments),
                "git_branch" => GitBranch(arguments),
                "git_log" => GitLog(arguments),
                "git_diff" => GitDiff(arguments),
                "git_reset" => GitReset(arguments),
                "git_stash" => GitStash(arguments),
                // GitHub Issue tools
                "github_create_issue" => GitHubCreateIssue(arguments).GetAwaiter().GetResult(),
                "github_list_issues" => GitHubListIssues(arguments).GetAwaiter().GetResult(),
                "github_get_issue" => GitHubGetIssue(arguments).GetAwaiter().GetResult(),
                "github_update_issue" => GitHubUpdateIssue(arguments).GetAwaiter().GetResult(),
                "github_add_comment" => GitHubAddComment(arguments).GetAwaiter().GetResult(),
                _ => Error($"Unknown tool: {name}")
            };
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine($"[GitPublisher] Error: {ex.Message}");
            return Error(ex.Message);
        }
    }

    private object GitStatus(JToken args)
    {
        var shortFormat = args["short"]?.Value<bool>() ?? false;
        var arguments = shortFormat ? "status --short" : "status";

        var (exitCode, stdout, stderr) = RunGit(arguments);

        if (exitCode != 0)
            return Error($"git status failed: {stderr}");

        return Success(string.IsNullOrWhiteSpace(stdout) ? "Working tree clean" : stdout);
    }

    private object GitAdd(JToken args)
    {
        var path = args["path"]?.ToString();
        if (string.IsNullOrEmpty(path))
            return Error("Path is required");

        var arguments = path == "-A" ? "add -A" : $"add \"{path}\"";
        var (exitCode, stdout, stderr) = RunGit(arguments);

        if (exitCode != 0)
            return Error($"git add failed: {stderr}");

        return Success($"Staged: {path}");
    }

    private object GitCommit(JToken args)
    {
        var message = args["message"]?.ToString();
        if (string.IsNullOrEmpty(message))
            return Error("Commit message is required");

        var author = args["author"]?.ToString();

        var arguments = new StringBuilder("commit");
        arguments.Append($" -m \"{message.Replace("\"", "\\\"")}\"");

        if (!string.IsNullOrEmpty(author))
            arguments.Append($" --author=\"{author}\"");

        var (exitCode, stdout, stderr) = RunGit(arguments.ToString());

        if (exitCode != 0)
        {
            if (stderr.Contains("nothing to commit"))
                return Success("Nothing to commit, working tree clean");
            return Error($"git commit failed: {stderr}");
        }

        return Success(stdout);
    }

    private object GitPush(JToken args)
    {
        var remote = args["remote"]?.ToString() ?? "origin";
        var branch = args["branch"]?.ToString();
        var setUpstream = args["set_upstream"]?.Value<bool>() ?? false;
        var force = args["force"]?.Value<bool>() ?? false;

        var arguments = new StringBuilder("push");

        if (setUpstream)
            arguments.Append(" -u");
        if (force)
            arguments.Append(" --force");

        arguments.Append($" {remote}");

        if (!string.IsNullOrEmpty(branch))
            arguments.Append($" {branch}");

        var (exitCode, stdout, stderr) = RunGit(arguments.ToString());

        if (exitCode != 0)
            return Error($"git push failed: {stderr}");

        // Git push output usually goes to stderr
        var output = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        return Success(string.IsNullOrWhiteSpace(output) ? "Push successful" : output);
    }

    private object GitPull(JToken args)
    {
        var remote = args["remote"]?.ToString() ?? "origin";
        var branch = args["branch"]?.ToString();
        var rebase = args["rebase"]?.Value<bool>() ?? false;

        var arguments = new StringBuilder("pull");

        if (rebase)
            arguments.Append(" --rebase");

        arguments.Append($" {remote}");

        if (!string.IsNullOrEmpty(branch))
            arguments.Append($" {branch}");

        var (exitCode, stdout, stderr) = RunGit(arguments.ToString());

        if (exitCode != 0)
            return Error($"git pull failed: {stderr}");

        return Success(string.IsNullOrWhiteSpace(stdout) ? "Already up to date" : stdout);
    }

    private object GitBranch(JToken args)
    {
        var action = args["action"]?.ToString()?.ToLower() ?? "list";
        var name = args["name"]?.ToString();
        var all = args["all"]?.Value<bool>() ?? false;

        string arguments;
        switch (action)
        {
            case "list":
                arguments = all ? "branch -a" : "branch";
                break;
            case "create":
                if (string.IsNullOrEmpty(name))
                    return Error("Branch name is required for create action");
                arguments = $"branch \"{name}\"";
                break;
            case "switch":
            case "checkout":
                if (string.IsNullOrEmpty(name))
                    return Error("Branch name is required for switch action");
                arguments = $"checkout \"{name}\"";
                break;
            case "delete":
                if (string.IsNullOrEmpty(name))
                    return Error("Branch name is required for delete action");
                arguments = $"branch -d \"{name}\"";
                break;
            default:
                return Error($"Unknown branch action: {action}");
        }

        var (exitCode, stdout, stderr) = RunGit(arguments);

        if (exitCode != 0)
            return Error($"git branch {action} failed: {stderr}");

        var output = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        return Success(string.IsNullOrWhiteSpace(output) ? $"Branch {action} completed" : output);
    }

    private object GitLog(JToken args)
    {
        var count = args["count"]?.Value<int>() ?? 10;
        var oneline = args["oneline"]?.Value<bool>() ?? true;
        var all = args["all"]?.Value<bool>() ?? false;

        var arguments = new StringBuilder($"log -n {count}");

        if (oneline)
            arguments.Append(" --oneline");
        if (all)
            arguments.Append(" --all");

        var (exitCode, stdout, stderr) = RunGit(arguments.ToString());

        if (exitCode != 0)
            return Error($"git log failed: {stderr}");

        return Success(string.IsNullOrWhiteSpace(stdout) ? "No commits found" : stdout);
    }

    private object GitDiff(JToken args)
    {
        var staged = args["staged"]?.Value<bool>() ?? false;
        var path = args["path"]?.ToString();
        var stat = args["stat"]?.Value<bool>() ?? false;

        var arguments = new StringBuilder("diff");

        if (staged)
            arguments.Append(" --cached");
        if (stat)
            arguments.Append(" --stat");
        if (!string.IsNullOrEmpty(path))
            arguments.Append($" -- \"{path}\"");

        var (exitCode, stdout, stderr) = RunGit(arguments.ToString());

        if (exitCode != 0)
            return Error($"git diff failed: {stderr}");

        return Success(string.IsNullOrWhiteSpace(stdout) ? "No differences" : stdout);
    }

    private object GitReset(JToken args)
    {
        var mode = args["mode"]?.ToString()?.ToLower() ?? "mixed";
        var target = args["target"]?.ToString() ?? "HEAD";

        if (mode != "soft" && mode != "mixed" && mode != "hard")
            return Error($"Invalid reset mode: {mode}. Use: soft, mixed, or hard");

        var arguments = $"reset --{mode} {target}";
        var (exitCode, stdout, stderr) = RunGit(arguments);

        if (exitCode != 0)
            return Error($"git reset failed: {stderr}");

        var output = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        return Success(string.IsNullOrWhiteSpace(output) ? $"Reset to {target} ({mode})" : output);
    }

    private object GitStash(JToken args)
    {
        var action = args["action"]?.ToString()?.ToLower() ?? "push";
        var message = args["message"]?.ToString();

        string arguments;
        switch (action)
        {
            case "push":
            case "save":
                arguments = string.IsNullOrEmpty(message) ? "stash push" : $"stash push -m \"{message}\"";
                break;
            case "pop":
                arguments = "stash pop";
                break;
            case "apply":
                arguments = "stash apply";
                break;
            case "list":
                arguments = "stash list";
                break;
            case "drop":
                arguments = "stash drop";
                break;
            case "clear":
                arguments = "stash clear";
                break;
            default:
                return Error($"Unknown stash action: {action}");
        }

        var (exitCode, stdout, stderr) = RunGit(arguments);

        if (exitCode != 0)
        {
            if (stderr.Contains("No stash entries found"))
                return Success("No stash entries found");
            if (stderr.Contains("No local changes to save"))
                return Success("No local changes to stash");
            return Error($"git stash {action} failed: {stderr}");
        }

        var output = string.IsNullOrWhiteSpace(stdout) ? stderr : stdout;
        return Success(string.IsNullOrWhiteSpace(output) ? $"Stash {action} completed" : output);
    }

    // ==================== GitHub API Methods ====================

    private (string owner, string repo)? GetRepoInfoFromRemote()
    {
        var (exitCode, stdout, _) = RunGit("remote get-url origin");
        if (exitCode != 0 || string.IsNullOrWhiteSpace(stdout))
            return null;

        var url = stdout.Trim();
        // Handle SSH format: git@github.com:owner/repo.git
        if (url.StartsWith("git@github.com:"))
        {
            var path = url.Substring("git@github.com:".Length).TrimEnd(".git".ToCharArray());
            var parts = path.Split('/');
            if (parts.Length >= 2)
                return (parts[0], parts[1]);
        }
        // Handle HTTPS format: https://github.com/owner/repo.git
        else if (url.Contains("github.com"))
        {
            var uri = new Uri(url);
            var segments = uri.AbsolutePath.Trim('/').TrimEnd(".git".ToCharArray()).Split('/');
            if (segments.Length >= 2)
                return (segments[0], segments[1]);
        }

        return null;
    }

    private (string owner, string repo) GetOwnerRepo(JToken args)
    {
        var owner = args["owner"]?.ToString();
        var repo = args["repo"]?.ToString();

        if (string.IsNullOrEmpty(owner) || string.IsNullOrEmpty(repo))
        {
            var repoInfo = GetRepoInfoFromRemote();
            if (repoInfo == null)
                throw new Exception("Could not determine repository owner/name. Please provide 'owner' and 'repo' parameters or ensure git remote 'origin' is set.");

            owner ??= repoInfo.Value.owner;
            repo ??= repoInfo.Value.repo;
        }

        return (owner, repo);
    }

    private async Task<object> GitHubCreateIssue(JToken args)
    {
        if (string.IsNullOrEmpty(_githubToken))
            return Error("GITHUB_TOKEN is required for creating issues");

        var (owner, repo) = GetOwnerRepo(args);
        var title = args["title"]?.ToString();
        if (string.IsNullOrEmpty(title))
            return Error("Issue title is required");

        var body = args["body"]?.ToString() ?? "";
        var labels = args["labels"]?.ToObject<string[]>() ?? Array.Empty<string>();
        var assignees = args["assignees"]?.ToObject<string[]>() ?? Array.Empty<string>();

        var payload = new
        {
            title,
            body,
            labels,
            assignees
        };

        var url = $"https://api.github.com/repos/{owner}/{repo}/issues";
        var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");

        Console.Error.WriteLine($"[GitPublisher] Creating issue in {owner}/{repo}: {title}");

        var response = await _httpClient.PostAsync(url, content);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
        {
            Console.Error.WriteLine($"[GitPublisher] GitHub API error: {response.StatusCode} - {responseBody}");
            return Error($"GitHub API error ({response.StatusCode}): {responseBody}");
        }

        var issue = JObject.Parse(responseBody);
        var issueNumber = issue["number"]?.Value<int>() ?? 0;
        var issueUrl = issue["html_url"]?.ToString() ?? "";

        return Success($"Issue #{issueNumber} created successfully!\nURL: {issueUrl}\nTitle: {title}");
    }

    private async Task<object> GitHubListIssues(JToken args)
    {
        if (string.IsNullOrEmpty(_githubToken))
            return Error("GITHUB_TOKEN is required for listing issues");

        var (owner, repo) = GetOwnerRepo(args);
        var state = args["state"]?.ToString() ?? "open";
        var labels = args["labels"]?.ToString() ?? "";
        var perPage = args["per_page"]?.Value<int>() ?? 10;

        var url = $"https://api.github.com/repos/{owner}/{repo}/issues?state={state}&per_page={perPage}";
        if (!string.IsNullOrEmpty(labels))
            url += $"&labels={Uri.EscapeDataString(labels)}";

        Console.Error.WriteLine($"[GitPublisher] Listing issues in {owner}/{repo}");

        var response = await _httpClient.GetAsync(url);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
            return Error($"GitHub API error ({response.StatusCode}): {responseBody}");

        var issues = JArray.Parse(responseBody);
        var sb = new StringBuilder();
        sb.AppendLine($"Issues in {owner}/{repo} ({state}):");
        sb.AppendLine();

        foreach (var issue in issues)
        {
            var number = issue["number"]?.Value<int>() ?? 0;
            var issueTitle = issue["title"]?.ToString() ?? "";
            var issueState = issue["state"]?.ToString() ?? "";
            var issueLabels = issue["labels"]?.Select(l => l["name"]?.ToString()).Where(l => l != null) ?? Enumerable.Empty<string>();
            var labelStr = issueLabels.Any() ? $" [{string.Join(", ", issueLabels)}]" : "";

            sb.AppendLine($"#{number} [{issueState}] {issueTitle}{labelStr}");
        }

        if (!issues.Any())
            sb.AppendLine("No issues found.");

        return Success(sb.ToString());
    }

    private async Task<object> GitHubGetIssue(JToken args)
    {
        if (string.IsNullOrEmpty(_githubToken))
            return Error("GITHUB_TOKEN is required for getting issue details");

        var (owner, repo) = GetOwnerRepo(args);
        var issueNumber = args["issue_number"]?.Value<int>() ?? 0;
        if (issueNumber == 0)
            return Error("issue_number is required");

        var url = $"https://api.github.com/repos/{owner}/{repo}/issues/{issueNumber}";

        Console.Error.WriteLine($"[GitPublisher] Getting issue #{issueNumber} in {owner}/{repo}");

        var response = await _httpClient.GetAsync(url);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
            return Error($"GitHub API error ({response.StatusCode}): {responseBody}");

        var issue = JObject.Parse(responseBody);
        var sb = new StringBuilder();

        sb.AppendLine($"Issue #{issue["number"]} - {issue["title"]}");
        sb.AppendLine($"State: {issue["state"]}");
        sb.AppendLine($"URL: {issue["html_url"]}");
        sb.AppendLine($"Created: {issue["created_at"]}");
        sb.AppendLine($"Author: {issue["user"]?["login"]}");

        var labels = issue["labels"]?.Select(l => l["name"]?.ToString()).Where(l => l != null);
        if (labels?.Any() == true)
            sb.AppendLine($"Labels: {string.Join(", ", labels)}");

        var assignees = issue["assignees"]?.Select(a => a["login"]?.ToString()).Where(a => a != null);
        if (assignees?.Any() == true)
            sb.AppendLine($"Assignees: {string.Join(", ", assignees)}");

        sb.AppendLine();
        sb.AppendLine("--- Body ---");
        sb.AppendLine(issue["body"]?.ToString() ?? "(no description)");

        return Success(sb.ToString());
    }

    private async Task<object> GitHubUpdateIssue(JToken args)
    {
        if (string.IsNullOrEmpty(_githubToken))
            return Error("GITHUB_TOKEN is required for updating issues");

        var (owner, repo) = GetOwnerRepo(args);
        var issueNumber = args["issue_number"]?.Value<int>() ?? 0;
        if (issueNumber == 0)
            return Error("issue_number is required");

        var payload = new Dictionary<string, object>();

        if (args["title"] != null)
            payload["title"] = args["title"].ToString();
        if (args["body"] != null)
            payload["body"] = args["body"].ToString();
        if (args["state"] != null)
            payload["state"] = args["state"].ToString();
        if (args["labels"] != null)
            payload["labels"] = args["labels"].ToObject<string[]>();

        if (!payload.Any())
            return Error("At least one field to update is required (title, body, state, or labels)");

        var url = $"https://api.github.com/repos/{owner}/{repo}/issues/{issueNumber}";
        var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");

        Console.Error.WriteLine($"[GitPublisher] Updating issue #{issueNumber} in {owner}/{repo}");

        var request = new HttpRequestMessage(new HttpMethod("PATCH"), url) { Content = content };
        var response = await _httpClient.SendAsync(request);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
            return Error($"GitHub API error ({response.StatusCode}): {responseBody}");

        var issue = JObject.Parse(responseBody);
        return Success($"Issue #{issueNumber} updated successfully!\nURL: {issue["html_url"]}");
    }

    private async Task<object> GitHubAddComment(JToken args)
    {
        if (string.IsNullOrEmpty(_githubToken))
            return Error("GITHUB_TOKEN is required for adding comments");

        var (owner, repo) = GetOwnerRepo(args);
        var issueNumber = args["issue_number"]?.Value<int>() ?? 0;
        if (issueNumber == 0)
            return Error("issue_number is required");

        var body = args["body"]?.ToString();
        if (string.IsNullOrEmpty(body))
            return Error("Comment body is required");

        var payload = new { body };
        var url = $"https://api.github.com/repos/{owner}/{repo}/issues/{issueNumber}/comments";
        var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");

        Console.Error.WriteLine($"[GitPublisher] Adding comment to issue #{issueNumber} in {owner}/{repo}");

        var response = await _httpClient.PostAsync(url, content);
        var responseBody = await response.Content.ReadAsStringAsync();

        if (!response.IsSuccessStatusCode)
            return Error($"GitHub API error ({response.StatusCode}): {responseBody}");

        var comment = JObject.Parse(responseBody);
        return Success($"Comment added successfully!\nURL: {comment["html_url"]}");
    }

    // ==================== Helper Methods ====================

    private static object Success(string text) => new
    {
        content = new[] { new { type = "text", text } },
        isError = false
    };

    private static object Error(string message) => new
    {
        content = new[] { new { type = "text", text = $"Error: {message}" } },
        isError = true
    };
}
