"""Post-completion verification suite."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from rafiki.issues import IssueFiler
from rafiki.models import VerificationResult, VerificationReport

logger = logging.getLogger("rafiki.verifier")


async def _run_cmd(cmd: list[str], cwd: Path | None = None, timeout: float = 120.0) -> tuple[int, str, str]:
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return (
            proc.returncode or 0,
            stdout.decode("utf-8", errors="replace").strip(),
            stderr.decode("utf-8", errors="replace").strip(),
        )
    except asyncio.TimeoutError:
        return (-1, "", f"Command timed out after {timeout}s")
    except FileNotFoundError:
        return (-1, "", f"Command not found: {cmd[0]}")


class Verifier:
    """Runs verification checks on the generated project."""

    def __init__(
        self,
        workspace_root: Path,
        project_key: str,
        issue_filer: IssueFiler,
    ):
        self.workspace_root = workspace_root
        self.project_key = project_key
        self.issue_filer = issue_filer
        self.project_dir = workspace_root / project_key

    async def run(self) -> VerificationReport:
        """Run all verification checks."""
        checks = [
            self._check_artifacts,
            self._check_open_issues,
            self._check_source_structure,
            self._check_build,
            self._check_tests,
            self._check_lint,
            self._check_api_starts,
            self._check_endpoints,
        ]
        results = []
        for i, check in enumerate(checks, 1):
            logger.info("Verification [%d/%d]: %s", i, len(checks), check.__doc__ or check.__name__)
            start = time.monotonic()
            try:
                result = await check()
            except Exception as exc:
                result = VerificationResult(
                    name=check.__name__.replace("_check_", ""),
                    passed=False,
                    detail=f"Exception: {exc}",
                )
            result.duration_ms = int((time.monotonic() - start) * 1000)
            results.append(result)

        overall = "PASS" if all(r.passed for r in results) else "FAIL"
        return VerificationReport(overall=overall, checks=results)

    async def _check_artifacts(self) -> VerificationResult:
        """AIDLC artifacts exist"""
        aidlc_dir = self.workspace_root / "aidlc-docs"
        if not aidlc_dir.exists():
            await self.issue_filer.file_bug(
                "AIDLC artifacts directory missing",
                "Expected aidlc-docs/ directory not found.",
                priority=1, source="verification",
            )
            return VerificationResult(name="artifacts_exist", passed=False, detail="aidlc-docs/ not found")

        md_files = list(aidlc_dir.rglob("*.md"))
        if not md_files:
            await self.issue_filer.file_bug(
                "No AIDLC artifacts found",
                "aidlc-docs/ exists but contains no markdown files.",
                priority=1, source="verification",
            )
            return VerificationResult(name="artifacts_exist", passed=False, detail="No .md files in aidlc-docs/")

        return VerificationResult(
            name="artifacts_exist", passed=True,
            detail=f"{len(md_files)} artifact(s) found",
        )

    async def _check_open_issues(self) -> VerificationResult:
        """No open Beads issues"""
        from rafiki.issues import _run_bd
        import json

        result = await _run_bd(["list", "--status", "open", "--json"], cwd=self.workspace_root)
        if not result:
            return VerificationResult(name="no_open_issues", passed=True, detail="No output from bd list")

        try:
            issues = json.loads(result)
            if isinstance(issues, dict):
                issues = issues.get("issues", [])
            # Filter to project-related issues (exclude Rafiki-filed)
            project_issues = [
                i for i in issues
                if "discovered-by:rafiki" not in (i.get("labels") or [])
            ]
            count = len(project_issues)
        except json.JSONDecodeError:
            return VerificationResult(name="no_open_issues", passed=True, detail="Could not parse bd output")

        if count > 0:
            await self.issue_filer.file_bug(
                f"{count} open Beads issues remaining",
                f"Expected 0 open pipeline issues, found {count}.",
                priority=1, source="verification",
            )
            return VerificationResult(name="no_open_issues", passed=False, detail=f"{count} open issues")

        return VerificationResult(name="no_open_issues", passed=True, detail="0 open issues")

    async def _check_source_structure(self) -> VerificationResult:
        """Source code structure"""
        expected = ["pyproject.toml"]
        src_dir = self.project_dir / "src"
        tests_dir = self.project_dir / "tests"

        missing = []
        for f in expected:
            if not (self.project_dir / f).exists():
                missing.append(f)
        if not src_dir.exists():
            missing.append("src/")
        if not tests_dir.exists():
            missing.append("tests/")

        if missing:
            await self.issue_filer.file_bug(
                f"Missing source structure: {', '.join(missing)}",
                f"Expected project files not found in {self.project_dir}:\n" + "\n".join(f"- {m}" for m in missing),
                priority=1, source="verification",
            )
            return VerificationResult(name="source_structure", passed=False, detail=f"Missing: {', '.join(missing)}")

        found = [str(p.relative_to(self.project_dir)) for p in self.project_dir.iterdir() if p.name in ("src", "tests", "pyproject.toml")]
        return VerificationResult(name="source_structure", passed=True, detail=", ".join(found))

    async def _check_build(self) -> VerificationResult:
        """Build succeeds (uv sync)"""
        if not self.project_dir.exists():
            return VerificationResult(name="build", passed=False, detail="Project directory not found")

        code, stdout, stderr = await _run_cmd(["uv", "sync"], cwd=self.project_dir)
        if code != 0:
            output = stderr or stdout
            await self.issue_filer.file_bug(
                "uv sync failed",
                f"Build failed with exit code {code}:\n{output[:1000]}",
                priority=0, source="verification",
            )
            return VerificationResult(name="build", passed=False, detail=f"Exit code {code}: {output[:200]}")

        return VerificationResult(name="build", passed=True, detail="uv sync succeeded")

    async def _check_tests(self) -> VerificationResult:
        """Tests pass (uv run pytest)"""
        if not self.project_dir.exists():
            return VerificationResult(name="tests", passed=False, detail="Project directory not found")

        code, stdout, stderr = await _run_cmd(["uv", "run", "pytest", "-v", "--tb=short"], cwd=self.project_dir, timeout=180.0)
        output = stdout or stderr
        if code != 0:
            await self.issue_filer.file_bug(
                f"pytest failed with exit code {code}",
                f"Test run failed:\n{output[:2000]}",
                priority=0, source="verification",
            )
            return VerificationResult(name="tests", passed=False, detail=f"Exit code {code}")

        return VerificationResult(name="tests", passed=True, detail=output.split("\n")[-1] if output else "passed")

    async def _check_lint(self) -> VerificationResult:
        """Linting (uv run ruff check)"""
        if not self.project_dir.exists():
            return VerificationResult(name="lint", passed=False, detail="Project directory not found")

        code, stdout, stderr = await _run_cmd(["uv", "run", "ruff", "check", "."], cwd=self.project_dir)
        output = stdout or stderr
        if code != 0:
            lines = output.strip().split("\n")
            violation_count = len([l for l in lines if l.strip() and not l.startswith("Found")])
            await self.issue_filer.file_task(
                f"ruff found {violation_count} lint violations",
                f"Linting output:\n{output[:2000]}",
                priority=2, source="verification",
            )
            return VerificationResult(name="lint", passed=False, detail=f"{violation_count} violations")

        return VerificationResult(name="lint", passed=True, detail="No violations")

    async def _check_api_starts(self) -> VerificationResult:
        """API starts (/health)"""
        if not self.project_dir.exists():
            return VerificationResult(name="api_starts", passed=False, detail="Project directory not found")

        # Start the API server
        port = 18765  # Use a high port to avoid conflicts
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "uvicorn",
            f"{self.project_key.replace('-', '_')}.app:app",
            "--port", str(port),
            "--host", "127.0.0.1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_dir,
        )

        try:
            # Wait for startup
            await asyncio.sleep(3)

            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"http://127.0.0.1:{port}/health")
                if resp.status_code == 200:
                    return VerificationResult(name="api_starts", passed=True, detail=f"200 OK on port {port}")
                else:
                    await self.issue_filer.file_bug(
                        f"API health check returned {resp.status_code}",
                        f"Expected 200, got {resp.status_code}: {resp.text[:500]}",
                        priority=0, source="verification",
                    )
                    return VerificationResult(name="api_starts", passed=False, detail=f"Status {resp.status_code}")
        except Exception as exc:
            await self.issue_filer.file_bug(
                "API failed to start",
                f"uvicorn could not start or health check failed: {exc}",
                priority=0, source="verification",
            )
            return VerificationResult(name="api_starts", passed=False, detail=str(exc))
        finally:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()

    async def _check_endpoints(self) -> VerificationResult:
        """Endpoint spot-checks"""
        # This check depends on the API being up, so we start it again
        if not self.project_dir.exists():
            return VerificationResult(name="endpoints", passed=False, detail="Project directory not found")

        port = 18766
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "uvicorn",
            f"{self.project_key.replace('-', '_')}.app:app",
            "--port", str(port),
            "--host", "127.0.0.1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_dir,
        )

        try:
            await asyncio.sleep(3)

            import httpx
            checks = [
                ("add(2,3)=5", "/api/v1/arithmetic/add", {"a": 2, "b": 3}, 5),
                ("sqrt(16)=4.0", "/api/v1/scientific/sqrt", {"value": 16}, 4.0),
                ("sin(0)=0.0", "/api/v1/scientific/sin", {"value": 0}, 0.0),
            ]
            passed = []
            failed = []

            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=10.0) as client:
                for label, path, body, expected in checks:
                    try:
                        resp = await client.post(path, json=body)
                        if resp.status_code == 200:
                            result_val = resp.json().get("result")
                            if result_val == expected or abs(float(result_val or 0) - expected) < 0.001:
                                passed.append(label)
                            else:
                                failed.append(f"{label} got {result_val}")
                        else:
                            failed.append(f"{label} status={resp.status_code}")
                    except Exception as exc:
                        failed.append(f"{label} error={exc}")

            if failed:
                await self.issue_filer.file_bug(
                    f"Endpoint spot-check failures: {', '.join(failed)}",
                    f"Passed: {len(passed)}, Failed: {len(failed)}\n" + "\n".join(f"- {f}" for f in failed),
                    priority=1, source="verification",
                )
                detail = f"{len(passed)}/{len(checks)} passed — {', '.join(failed)}"
                return VerificationResult(name="endpoints", passed=False, detail=detail)

            detail = f"{len(passed)}/{len(checks)} correct — {' ✓  '.join(passed)} ✓"
            return VerificationResult(name="endpoints", passed=True, detail=detail)

        except Exception as exc:
            return VerificationResult(name="endpoints", passed=False, detail=f"Could not run spot-checks: {exc}")
        finally:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
