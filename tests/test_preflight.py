#!/usr/bin/env python3
"""Behavioral tests for openbot-tenant-preflight. Run: python3 -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "openbot-tenant-preflight")
CLEAN = os.path.join(ROOT, "examples", "in", "fintech")
BROKEN = os.path.join(ROOT, "examples", "in", "broken")


def run(*args):
    proc = subprocess.run(
        [sys.executable, BIN, *args], capture_output=True, text=True, timeout=60
    )
    return proc


def run_json(*args):
    proc = run(*args, "--json")
    return proc, json.loads(proc.stdout)


class PackageCheckTests(unittest.TestCase):
    def test_clean_package_exits_zero(self):
        proc, data = run_json("check", CLEAN)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertTrue(data["ok"])
        self.assertEqual(data["summary"]["errors"], 0)

    def test_clean_package_counts_agents(self):
        _, data = run_json("check", CLEAN)
        self.assertEqual(data["summary"]["agents"], 3)

    def test_broken_package_exits_one(self):
        proc, data = run_json("check", BROKEN)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(data["ok"])

    def test_reserved_agent_id_is_refused(self):
        _, data = run_json("check", BROKEN)
        self.assertIn("agent-id-reserved", {f["code"] for f in data["findings"]})

    def test_duplicate_agent_id_across_files_is_refused(self):
        _, data = run_json("check", BROKEN)
        dupes = [f for f in data["findings"] if f["code"] == "agent-id-duplicate"]
        self.assertEqual(len(dupes), 1)
        self.assertIn("agents.yaml", dupes[0]["message"] + dupes[0]["file"] + "agents.yaml")

    def test_unknown_skill_slug_is_refused(self):
        _, data = run_json("check", BROKEN)
        self.assertIn("agent-skill-unknown", {f["code"] for f in data["findings"]})

    def test_unknown_channel_agent_is_refused(self):
        _, data = run_json("check", BROKEN)
        hits = [f for f in data["findings"] if f["code"] == "channel-agent-unknown"]
        self.assertEqual(len(hits), 1)
        self.assertIn("ghost-agent", hits[0]["message"])

    def test_model_provider_enum_is_refused(self):
        _, data = run_json("check", BROKEN)
        self.assertIn("model-provider-invalid", {f["code"] for f in data["findings"]})

    def test_remote_agent_without_endpoint_is_warning_not_error(self):
        _, data = run_json("check", CLEAN)
        codes = {(f["severity"], f["code"]) for f in data["findings"]}
        self.assertIn(("warning", "agent-omitted"), codes)
        self.assertTrue(data["ok"])

    def test_overlong_title_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            shutil.copytree(CLEAN, pkg)
            path = os.path.join(pkg, "agents.yaml")
            with open(path, encoding="utf-8") as handle:
                text = handle.read()
            text = text.replace("title: Everyday Work", "title: " + "x" * 121)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            proc, data = run_json("check", pkg)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("agent-title-invalid", {f["code"] for f in data["findings"]})

    def test_skill_tool_ref_shape_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            shutil.copytree(CLEAN, pkg)
            path = os.path.join(pkg, "skills.yaml")
            with open(path, encoding="utf-8") as handle:
                text = handle.read().replace("- drive/search", "- not-a-ref")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
            proc, data = run_json("check", pkg)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("skill-tool-ref-invalid", {f["code"] for f in data["findings"]})

    def test_json_output_is_parseable_from_stdout(self):
        proc = run("check", CLEAN, "--json")
        json.loads(proc.stdout)
        self.assertEqual(proc.stderr, "")


class CatalogCheckTests(unittest.TestCase):
    def test_catalog_reports_staged_and_installed(self):
        proc, data = run_json("catalog", CLEAN)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(data["summary"]["catalog_files"], 2)
        self.assertEqual(data["summary"]["staged"], 1)
        self.assertIn("catalog-already-installed", {f["code"] for f in data["findings"]})

    def test_catalog_refuses_a_file_the_loader_would_reject(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = os.path.join(tmp, "pkg")
            shutil.copytree(CLEAN, pkg)
            path = os.path.join(pkg, "catalog", "new-hire.yaml")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "id: policy\nname: New Hire\ntitle: People\n"
                "role_description: Onboard a new hire.\ntype: built-in\n"
                    "system_prompt: Say hello.\n"
                )
            proc, data = run_json("catalog", pkg)
            self.assertEqual(proc.returncode, 1)
            self.assertIn("agent-id-reserved", {f["code"] for f in data["findings"]})


class UsageTests(unittest.TestCase):
    def test_missing_directory_is_usage_error(self):
        proc = run("check", "/nonexistent/package")
        self.assertEqual(proc.returncode, 2)

    def test_directory_without_agents_yaml_is_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run("check", tmp)
            self.assertEqual(proc.returncode, 2)

    def test_bad_subcommand_is_usage_error(self):
        proc = run("frobnicate", CLEAN)
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
