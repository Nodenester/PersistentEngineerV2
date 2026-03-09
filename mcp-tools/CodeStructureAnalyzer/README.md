# CodeStructureAnalyzer

A token-efficient code structure analyzer that extracts minimal but essential information from codebases. Perfect for feeding to AI models to understand project structure quickly.

## What It Produces

1. **Full folder tree** - Visual structure of the entire project
2. **File type summary** - Count of each file type (CSS, images, etc.)
3. **Detailed code parsing** - Only for code files that matter

## Example Output

```
# Project: MyApp
Total files: 45

## Structure
```
MyApp/
├── Controllers/ (3 files)
│   └── [3.cs]
├── Models/ (5 files)
│   └── [5.cs]
├── wwwroot/ (15 files)
│   ├── css/ (3 files)
│   │   └── [3.css]
│   └── images/ (10 files)
│       └── [8.png, 2.svg]
├── Program.cs
└── MyApp.csproj
```

## File Types
  .cs: 12 (C#)
  .css: 3 (CSS)
  .png: 8 (Image)
  .json: 2 (JSON)
  ...

## C# (12)

### Controllers/HomeController.cs
using: Microsoft.AspNetCore.Mvc
ns: MyApp.Controllers
public class HomeController : Controller
  public IActionResult Index()
  public IActionResult About()
```

## What Gets Parsed vs Listed

### Parsed in Detail (signatures only, no implementation)
- **C#** (.cs) - Classes, interfaces, methods, properties
- **JavaScript/TypeScript** (.js, .ts, .jsx, .tsx) - Classes, functions, imports
- **Python** (.py) - Classes, functions, imports
- **Razor** (.razor, .cshtml) - Routes, parameters, injected services
- **JSON** - Structure overview (limited depth)
- **XML/.csproj** - SDK, target framework, packages

### Listed Only (file exists, not parsed)
- **Styles**: .css, .scss, .sass, .less
- **Images**: .png, .jpg, .gif, .svg, .ico, .webp
- **Fonts**: .woff, .woff2, .ttf, .eot
- **Docs**: .md, .txt
- **Other**: Audio, video, archives, etc.

## Usage

```bash
# Analyze a folder (output to console)
codeparse /path/to/project

# Analyze and save to file
codeparse /path/to/project output.txt
```

## Building

```bash
dotnet restore
dotnet build -c Release
```

## Ignored Folders

Automatically skips:
- bin, obj, node_modules, .git, .vs, .idea
- packages, TestResults, dist, build, out

## Why Token-Efficient?

| Content | Raw | Parsed |
|---------|-----|--------|
| 300-line C# file | ~8000 tokens | ~200 tokens |
| CSS files | ~3000 tokens | 0 (listed) |
| Images | N/A | 0 (listed) |

**~95%+ token reduction** while keeping all architectural information!
