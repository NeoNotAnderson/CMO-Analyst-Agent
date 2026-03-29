"""
Evaluation Report Generator

Generates comprehensive reports from evaluation results in multiple formats:
- HTML with charts and visualizations
- Markdown for documentation
- JSON for programmatic access
- CSV for data analysis

Usage:
    from evaluation.workflows import generate_report

    generate_report(
        results=evaluation_results,
        output_path='reports/eval_2024_01_15.html',
        format='html'
    )
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


def generate_html_report(
    results: Dict[str, Any],
    output_path: str,
    title: Optional[str] = None
) -> str:
    """
    Generate HTML report with visualizations.

    Args:
        results: Evaluation results dict
        output_path: Path to save HTML report
        title: Report title (auto-generated if None)

    Returns:
        Path to generated report
    """
    if title is None:
        title = f"Evaluation Report - {results.get('experiment_name', 'Unnamed')}"

    summary = results.get('summary', {})
    evaluator_stats = summary.get('evaluator_stats', {})

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            margin: 0 0 10px 0;
            font-size: 32px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 14px;
        }}
        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .card {{
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .card .value {{
            font-size: 36px;
            font-weight: bold;
            color: #667eea;
        }}
        .evaluator-section {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .evaluator-section h2 {{
            margin: 0 0 20px 0;
            color: #333;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}
        .evaluator-item {{
            margin-bottom: 30px;
            padding-bottom: 30px;
            border-bottom: 1px solid #eee;
        }}
        .evaluator-item:last-child {{
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }}
        .evaluator-item h3 {{
            margin: 0 0 15px 0;
            color: #333;
            font-size: 20px;
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }}
        .metric {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 6px;
        }}
        .metric-label {{
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            margin-top: 5px;
        }}
        .progress-bar {{
            width: 100%;
            height: 30px;
            background: #e9ecef;
            border-radius: 15px;
            overflow: hidden;
            margin-top: 10px;
        }}
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
            transition: width 0.3s ease;
        }}
        .status-badge {{
            display: inline-block;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .status-pass {{
            background: #d4edda;
            color: #155724;
        }}
        .status-fail {{
            background: #f8d7da;
            color: #721c24;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <div class="meta">
            <strong>Dataset:</strong> {results.get('dataset_name', 'N/A')} &nbsp;|&nbsp;
            <strong>Timestamp:</strong> {results.get('timestamp', 'N/A')} &nbsp;|&nbsp;
            <strong>Experiment:</strong> {results.get('experiment_name', 'N/A')}
        </div>
    </div>

    <div class="summary-cards">
        <div class="card">
            <h3>Total Examples</h3>
            <div class="value">{summary.get('total_examples', 0)}</div>
        </div>
        <div class="card">
            <h3>Overall Pass Rate</h3>
            <div class="value">{summary.get('overall_pass_rate', 0):.1%}</div>
        </div>
        <div class="card">
            <h3>Status</h3>
            <div class="value">
                <span class="status-badge {'status-pass' if summary.get('overall_pass_rate', 0) >= 0.80 else 'status-fail'}">
                    {'PASS' if summary.get('overall_pass_rate', 0) >= 0.80 else 'NEEDS WORK'}
                </span>
            </div>
        </div>
    </div>

    <div class="evaluator-section">
        <h2>Evaluator Results</h2>
"""

    # Add each evaluator's results
    for evaluator_name, stats in evaluator_stats.items():
        if stats.get('count', 0) == 0:
            continue

        mean = stats.get('mean', 0)
        pass_rate = stats.get('pass_rate', 0)
        threshold = stats.get('threshold', 0.7)
        is_pass = pass_rate >= 0.80

        evaluator_display = evaluator_name.replace('_', ' ').title()

        html += f"""
        <div class="evaluator-item">
            <h3>{evaluator_display}</h3>
            <span class="status-badge {'status-pass' if is_pass else 'status-fail'}">
                {'PASS' if is_pass else 'NEEDS WORK'}
            </span>

            <div class="metrics">
                <div class="metric">
                    <div class="metric-label">Mean Score</div>
                    <div class="metric-value" style="color: {'#28a745' if mean >= threshold else '#dc3545'};">{mean:.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Min Score</div>
                    <div class="metric-value">{stats.get('min', 0):.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Max Score</div>
                    <div class="metric-value">{stats.get('max', 0):.2f}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Threshold</div>
                    <div class="metric-value">{threshold:.2f}</div>
                </div>
            </div>

            <div class="progress-bar">
                <div class="progress-fill" style="width: {pass_rate * 100}%">
                    {pass_rate:.1%} Pass Rate ({stats.get('pass_count', 0)}/{stats.get('count', 0)})
                </div>
            </div>
        </div>
"""

    html += """
    </div>

    <div class="footer">
        <p>Generated by CMO Analyst Agent Evaluation System</p>
        <p>View detailed results in <a href="https://smith.langchain.com" target="_blank">LangSmith</a></p>
    </div>
</body>
</html>
"""

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(html)

    return str(output_path)


def generate_markdown_report(
    results: Dict[str, Any],
    output_path: str,
    title: Optional[str] = None
) -> str:
    """
    Generate Markdown report for documentation.

    Args:
        results: Evaluation results dict
        output_path: Path to save Markdown report
        title: Report title (auto-generated if None)

    Returns:
        Path to generated report
    """
    if title is None:
        title = f"Evaluation Report - {results.get('experiment_name', 'Unnamed')}"

    summary = results.get('summary', {})
    evaluator_stats = summary.get('evaluator_stats', {})

    md = f"""# {title}

**Dataset:** {results.get('dataset_name', 'N/A')}
**Experiment:** {results.get('experiment_name', 'N/A')}
**Timestamp:** {results.get('timestamp', 'N/A')}

---

## Summary

- **Total Examples:** {summary.get('total_examples', 0)}
- **Overall Pass Rate:** {summary.get('overall_pass_rate', 0):.1%}
- **Status:** {'✅ PASS' if summary.get('overall_pass_rate', 0) >= 0.80 else '⚠️ NEEDS WORK'}

---

## Evaluator Results

"""

    # Add table
    md += "| Evaluator | Mean | Min | Max | Pass Rate | Status |\n"
    md += "|-----------|------|-----|-----|-----------|--------|\n"

    for evaluator_name, stats in evaluator_stats.items():
        if stats.get('count', 0) == 0:
            continue

        evaluator_display = evaluator_name.replace('_', ' ').title()
        mean = f"{stats.get('mean', 0):.2f}"
        min_val = f"{stats.get('min', 0):.2f}"
        max_val = f"{stats.get('max', 0):.2f}"
        pass_rate = f"{stats.get('pass_rate', 0):.1%}"
        status = "✅ Pass" if stats.get('pass_rate', 0) >= 0.80 else "⚠️ Needs Work"

        md += f"| {evaluator_display} | {mean} | {min_val} | {max_val} | {pass_rate} | {status} |\n"

    md += "\n---\n\n"

    # Add detailed breakdown
    md += "## Detailed Breakdown\n\n"

    for evaluator_name, stats in evaluator_stats.items():
        if stats.get('count', 0) == 0:
            continue

        evaluator_display = evaluator_name.replace('_', ' ').title()
        md += f"### {evaluator_display}\n\n"
        md += f"- **Mean Score:** {stats.get('mean', 0):.2f}\n"
        md += f"- **Min Score:** {stats.get('min', 0):.2f}\n"
        md += f"- **Max Score:** {stats.get('max', 0):.2f}\n"
        md += f"- **Threshold:** {stats.get('threshold', 0.7):.2f}\n"
        md += f"- **Pass Count:** {stats.get('pass_count', 0)}/{stats.get('count', 0)}\n"
        md += f"- **Pass Rate:** {stats.get('pass_rate', 0):.1%}\n"
        md += f"- **Status:** {'✅ Pass' if stats.get('pass_rate', 0) >= 0.80 else '⚠️ Needs Work'}\n\n"

    md += "---\n\n"
    md += "*Generated by CMO Analyst Agent Evaluation System*\n"
    md += "*View detailed results in [LangSmith](https://smith.langchain.com)*\n"

    # Write to file
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.write(md)

    return str(output_path)


def generate_report(
    results: Dict[str, Any],
    output_path: str,
    format: str = 'html',
    title: Optional[str] = None
) -> str:
    """
    Generate evaluation report in specified format.

    Args:
        results: Evaluation results dict from run_full_evaluation
        output_path: Path to save report
        format: 'html', 'markdown', 'json', or 'csv'
        title: Report title (auto-generated if None)

    Returns:
        Path to generated report
    """
    if format == 'html':
        return generate_html_report(results, output_path, title)

    elif format == 'markdown' or format == 'md':
        return generate_markdown_report(results, output_path, title)

    elif format == 'json':
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        serializable_results = {
            'experiment_name': results.get('experiment_name'),
            'dataset_name': results.get('dataset_name'),
            'timestamp': results.get('timestamp'),
            'summary': results.get('summary')
        }

        with open(output_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)

        return str(output_path)

    elif format == 'csv':
        import csv

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['Evaluator', 'Mean', 'Min', 'Max', 'Pass Rate', 'Threshold', 'Status'])

            # Data
            for evaluator_name, stats in results['summary']['evaluator_stats'].items():
                if stats.get('count', 0) > 0:
                    writer.writerow([
                        evaluator_name,
                        f"{stats.get('mean', 0):.2f}",
                        f"{stats.get('min', 0):.2f}",
                        f"{stats.get('max', 0):.2f}",
                        f"{stats.get('pass_rate', 0):.2%}",
                        f"{stats.get('threshold', 0.7):.2f}",
                        'PASS' if stats.get('pass_rate', 0) >= 0.80 else 'NEEDS WORK'
                    ])

        return str(output_path)

    else:
        raise ValueError(f"Unknown format: {format}")


if __name__ == '__main__':
    # Example usage
    print("Report Generator - Example\n")
    print("=" * 70)

    # Create sample results
    sample_results = {
        'experiment_name': 'eval_golden_20240115',
        'dataset_name': 'cmo-analyst-golden-v1',
        'timestamp': datetime.now().isoformat(),
        'summary': {
            'total_examples': 10,
            'overall_pass_rate': 0.85,
            'evaluator_stats': {
                'document_relevance': {
                    'count': 10,
                    'mean': 0.92,
                    'min': 0.75,
                    'max': 1.0,
                    'threshold': 0.70,
                    'pass_count': 9,
                    'pass_rate': 0.90
                },
                'answer_faithfulness': {
                    'count': 10,
                    'mean': 0.88,
                    'min': 0.70,
                    'max': 0.95,
                    'threshold': 0.80,
                    'pass_count': 8,
                    'pass_rate': 0.80
                },
                'answer_helpfulness': {
                    'count': 10,
                    'mean': 0.85,
                    'min': 0.65,
                    'max': 0.95,
                    'threshold': 0.70,
                    'pass_count': 9,
                    'pass_rate': 0.90
                },
                'answer_correctness': {
                    'count': 10,
                    'mean': 0.82,
                    'min': 0.60,
                    'max': 0.95,
                    'threshold': 0.80,
                    'pass_count': 8,
                    'pass_rate': 0.80
                }
            }
        }
    }

    # Generate reports in all formats
    output_dir = Path(__file__).parent / 'example_reports'
    output_dir.mkdir(exist_ok=True)

    print("\nGenerating example reports...\n")

    html_path = generate_report(sample_results, str(output_dir / 'report.html'), 'html')
    print(f"✅ HTML report: {html_path}")

    md_path = generate_report(sample_results, str(output_dir / 'report.md'), 'markdown')
    print(f"✅ Markdown report: {md_path}")

    json_path = generate_report(sample_results, str(output_dir / 'report.json'), 'json')
    print(f"✅ JSON report: {json_path}")

    csv_path = generate_report(sample_results, str(output_dir / 'report.csv'), 'csv')
    print(f"✅ CSV report: {csv_path}")

    print(f"\n{'='*70}\n")
