# GitHub Actions CI/CD Integration

## Enterprise Watchlist Test Automation

The Mork F.E.T.C.H Bot includes automated testing via GitHub Actions to ensure enterprise-grade reliability across all deployments.

### Workflow Configuration

**File:** `.github/workflows/watchlist-test.yml`

The CI workflow automatically runs on:
- Push to any branch
- Pull request creation/updates

### Test Matrix

The workflow tests across multiple configurations:

#### Python Versions
- Python 3.11 (production)
- Python 3.12 (latest)

#### Test Modes
- **Strict Mode** (`STRICT=1`): Requires real data values, no "?" placeholders allowed
- **Lenient Mode** (`STRICT=0`): Allows graceful degradation with "?" for offline sources

### Test Execution

Each CI run validates:
1. **All 6 Watchlist Modes**: supply, fdv, holders, prices, caps, volumes
2. **Sorting Functionality**: Ascending and descending sort validation
3. **Enterprise Optimization Features**:
   - Parallel processing with ThreadPoolExecutor
   - TTL caching with cross-mode value reuse
   - Timeout protection (8-second CI timeout)
   - Advanced row parsing with regex fallback
   - Graceful degradation handling

### Environment Configuration

```yaml
env:
  TEST_TIMEOUT: 8
  STRICT: ${{ matrix.test-mode == 'strict' && '1' || '0' }}
```

### Expected Results

✅ **Success Criteria:**
- All tests pass with "PASS" result
- No timeout errors during execution
- Both strict and lenient modes validate successfully
- Test runner script validation passes

❌ **Failure Indicators:**
- Any test shows "FAIL(n)" with error count
- Timeout errors during test execution
- Import or dependency resolution issues

### Local Development

To run the same tests locally:

```bash
# Strict mode (production validation)
STRICT=1 TEST_TIMEOUT=8 python3 tests/test_watchlist.py

# Lenient mode (development validation)
STRICT=0 TEST_TIMEOUT=8 python3 tests/test_watchlist.py

# Full test suite
./tests/run_tests.sh
```

### Integration Benefits

1. **Continuous Validation**: Every code change automatically validates enterprise features
2. **Multi-Environment Testing**: Ensures compatibility across Python versions
3. **Deployment Confidence**: Pre-deployment validation prevents production issues
4. **Documentation Sync**: CI failures indicate need for documentation updates

This automated testing framework ensures the enterprise watchlist optimization system maintains production-grade reliability across all deployments and code changes.