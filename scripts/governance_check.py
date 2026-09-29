#!/usr/bin/env python3

import argparse
import pathlib
import sys

import yaml


SEVERITY_ORDER = {
    "INFO": 0,
    "WARNING": 1,
    "HIGH": 2,
    "BLOCKER": 3,
}


def load_config(config_path):
    """Load governance rules from YAML."""

    if not config_path.exists():
        raise FileNotFoundError(
            f"Governance configuration not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def evaluate_file_exists(rule, root):
    """
    Generic file_exists rule evaluator.

    The actual paths and matching behaviour are defined
    entirely in governance-rules.yaml.
    """

    enforcement = rule.get("enforcement", {})

    paths = enforcement.get("paths", [])
    match_mode = enforcement.get("match", "all").lower()

    if not paths:
        return {
            "passed": False,
            "message": "No paths configured for file_exists rule.",
        }

    results = []

    for configured_path in paths:
        path = root / configured_path

        results.append({
            "path": configured_path,
            "exists": path.is_file(),
        })

    if match_mode == "any":
        passed = any(result["exists"] for result in results)

    elif match_mode == "all":
        passed = all(result["exists"] for result in results)

    else:
        return {
            "passed": False,
            "message": f"Unsupported match mode: {match_mode}",
        }

    existing = [
        result["path"]
        for result in results
        if result["exists"]
    ]

    missing = [
        result["path"]
        for result in results
        if not result["exists"]
    ]

    if passed:
        return {
            "passed": True,
            "message": (
                "Requirement satisfied: "
                + ", ".join(existing)
            ),
        }

    return {
        "passed": False,
        "message": (
            "Required file condition not satisfied. "
            f"Checked: {', '.join(paths)}"
        ),
    }


# ---------------------------------------------------------
# Enforcement engine registry
# ---------------------------------------------------------

ENFORCEMENT_HANDLERS = {
    "file_exists": evaluate_file_exists,
}


def evaluate_rule(rule, root):
    """
    Evaluate one governance rule.

    No rule IDs are hard-coded here.
    """

    enforcement = rule.get("enforcement", {})

    enforcement_type = enforcement.get("type")

    if not enforcement_type:
        return {
            "passed": False,
            "message": "Rule does not define enforcement.type",
        }

    handler = ENFORCEMENT_HANDLERS.get(enforcement_type)

    if not handler:
        return {
            "passed": False,
            "message": (
                f"Unsupported enforcement type: "
                f"{enforcement_type}"
            ),
        }

    return handler(rule, root)


def main():

    parser = argparse.ArgumentParser(
        description="MuleSoft Engineering Governance Framework"
    )

    parser.add_argument(
        "--root",
        default=".",
        help="Repository root"
    )

    parser.add_argument(
        "--config",
        default="config/governance-rules.yaml",
        help="Governance rule configuration"
    )

    args = parser.parse_args()

    root = pathlib.Path(args.root).resolve()

    config_path = pathlib.Path(args.config)

    if not config_path.is_absolute():
        config_path = root / config_path

    try:
        config = load_config(config_path)

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    defaults = config.get("defaults", {})

    fail_on = defaults.get(
        "fail_on",
        "HIGH"
    ).upper()

    threshold = SEVERITY_ORDER.get(
        fail_on,
        SEVERITY_ORDER["HIGH"]
    )

    print()
    print("=" * 70)
    print("MuleSoft Engineering Governance Framework")
    print("=" * 70)

    print(
        f"Framework Version : "
        f"{config.get('framework_version', 'unknown')}"
    )

    print(
        f"Rule Pack         : "
        f"{config.get('rule_pack', 'unknown')}"
    )

    print(
        f"Fail Threshold    : "
        f"{fail_on}"
    )

    print("=" * 70)
    print()

    findings = []

    rules = config.get("rules", [])

    enabled_rules = [
        rule
        for rule in rules
        if rule.get("enabled", True)
    ]

    for rule in enabled_rules:

        rule_id = rule.get("id", "UNKNOWN")
        title = rule.get("title", "")
        severity = rule.get(
            "severity",
            "WARNING"
        ).upper()

        result = evaluate_rule(
            rule,
            root
        )

        if result["passed"]:

            print(
                f"[PASS] "
                f"{rule_id} - "
                f"{title}"
            )

            print(
                f"       {result['message']}"
            )

        else:

            finding = {
                "rule": rule_id,
                "severity": severity,
                "title": title,
                "message": result["message"],
                "remediation": rule.get(
                    "remediation",
                    ""
                ),
            }

            findings.append(finding)

            print(
                f"[{severity}] "
                f"{rule_id} - "
                f"{title}"
            )

            print(
                f"       {result['message']}"
            )

            if finding["remediation"]:

                print(
                    f"       Remediation: "
                    f"{finding['remediation']}"
                )

        print()

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    blocking_findings = []

    for finding in findings:

        severity_value = SEVERITY_ORDER.get(
            finding["severity"],
            0
        )

        if severity_value >= threshold:
            blocking_findings.append(finding)

    print("=" * 70)
    print("Governance Summary")
    print("=" * 70)

    print(
        f"Rules evaluated : "
        f"{len(enabled_rules)}"
    )

    print(
        f"Passed          : "
        f"{len(enabled_rules) - len(findings)}"
    )

    print(
        f"Failed          : "
        f"{len(findings)}"
    )

    print(
        f"Blocking        : "
        f"{len(blocking_findings)}"
    )

    print()

    if blocking_findings:

        print("Governance Result: FAIL")
        return 1

    print("Governance Result: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())