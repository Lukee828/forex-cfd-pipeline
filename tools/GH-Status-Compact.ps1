# tools/GH-Status-Compact.ps1 — robust CreatedAt → UTC normalization
$ErrorActionPreference = "Stop"

function Convert-ToUtcString([string]$s) {
  $styles = [System.Globalization.DateTimeStyles]::AssumeUniversal `
          -bor [System.Globalization.DateTimeStyles]::AdjustToUniversal
  $fmtOut = 'yyyy-MM-dd HH:mm:ss'
  $dto = [datetimeoffset]::MinValue

  # 1) Try exact ISO/RFC3339
  $iso = @('yyyy-MM-ddTHH:mm:ssK','yyyy-MM-ddTHH:mm:ss.fffK')
  if ([datetimeoffset]::TryParseExact($s,$iso,[Globalization.CultureInfo]::InvariantCulture,$styles,[ref]$dto)) {
    return $dto.UtcDateTime.ToString($fmtOut) + ' UTC'
  }

  # 2) Try common US/EU patterns explicitly (what GitHub often emits)
  $common = @(
    'MM/dd/yyyy HH:mm:ss', 'M/d/yyyy HH:mm:ss',               # US 24h
    'MM/dd/yyyy h:mm:ss tt', 'M/d/yyyy h:mm:ss tt',           # US 12h
    'dd/MM/yyyy HH:mm:ss', 'd/M/yyyy HH:mm:ss',               # EU 24h
    'yyyy-MM-dd HH:mm:ss'                                     # plain ISO date + space
  )
  if ([datetimeoffset]::TryParseExact($s,$common,[Globalization.CultureInfo]::InvariantCulture,$styles,[ref]$dto)) {
    return $dto.UtcDateTime.ToString($fmtOut) + ' UTC'
  }

  # 3) Fallback: generic parse with a couple of cultures
  foreach ($ciName in @('en-US','pl-PL','')) {
    try {
      $ci = if ($ciName) { [Globalization.CultureInfo]::new($ciName) } else { [Globalization.CultureInfo]::InvariantCulture }
      $dto = [datetimeoffset]::Parse($s,$ci,$styles)
      return $dto.UtcDateTime.ToString($fmtOut) + ' UTC'
    } catch {}
  }

  # Last resort: return original string
  return $s
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
$rows = gh run list --branch $branch -L 40 --json workflowName,status,conclusion,createdAt,url | ConvertFrom-Json

"{0,-28} {1,-11} {2,-11} {3,-20} {4}" -f "Workflow","Status","Conclusion","Created(UTC)","URL"
"".PadRight(115,'-') | Write-Host

$rows |
  Sort-Object workflowName,createdAt -Descending |
  Group-Object workflowName |
  ForEach-Object {
    $r = $_.Group | Select-Object -First 1
    $when = Convert-ToUtcString $r.createdAt
    "{0,-28} {1,-11} {2,-11} {3,-20} {4}" -f $r.workflowName, $r.status, ($r.conclusion ?? "-"), $when, $r.url
  }
