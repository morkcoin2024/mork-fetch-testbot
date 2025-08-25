# Mork F.E.T.C.H Bot Test Suite

## Enterprise Watchlist Optimization Tests

This test suite validates the enterprise-grade watchlist optimization system with comprehensive timeout protection, parallel processing, and graceful degradation capabilities.

### Test Coverage

#### Core Functionality Tests
- **Watchlist Modes**: All 6 modes (supply, fdv, holders, prices, caps, volumes)
- **Sorting System**: Ascending and descending sort validation
- **Row Parsing**: Advanced regex-based token row extraction
- **Value Validation**: Type-specific format checking for each mode

#### Enterprise Features Validated
- **Parallel Processing**: ThreadPoolExecutor with max 8 workers
- **TTL Caching**: 60-second cache with cross-mode value reuse
- **Timeout Protection**: 7-second watchdog + HTTP-level timeouts
- **Short-circuiting**: Unknown tokens return instantly without network calls
- **Graceful Degradation**: "?" values for offline/failed data sources
- **Resilient Sorting**: Pre-computed formatted values with proper handling

### Running Tests

#### Using Makefile (Recommended)
```bash
# Show available targets
make help

# Run enterprise watchlist tests (default: strict mode)
make test-watchlist

# Run strict mode tests (requires real data)
make test-watchlist-strict

# Run lenient mode tests (allows "?" values)
make test-watchlist-lenient

# Run both test modes
make test-all
```

#### Direct Execution
```bash
# Quick test with scanners enabled
FETCH_ENABLE_SCANNERS=1 python tests/test_watchlist.py

# Full test suite
./tests/run_tests.sh
```

#### CI/CD Integration
```bash
# GitHub Actions compatible
STRICT=1 TEST_TIMEOUT=8 python3 tests/test_watchlist.py
```

#### Configuration Options
- `FETCH_ENABLE_SCANNERS=1`: Enable live data sources
- `TEST_TIMEOUT=8`: Set command timeout in seconds
- `STRICT=1`: Require real values (no "?" allowed)
- `STRICT=0`: Allow graceful degradation with "?" values

**Note:** Tests include automatic path resolution, eliminating the need for manual PYTHONPATH configuration.

### Test Results Interpretation

#### Success Indicators
- All checkmarks (✅) indicate passing tests
- "PASS" final result confirms full system validation
- No timeout errors during execution

#### Expected Behaviors
- SOL token shows data values or "?" (both acceptable)
- Unknown tokens consistently show "?" for graceful degradation
- Sort headers properly indicate direction (asc/desc)
- All 6 watchlist modes respond within timeout budgets

### System Architecture Validation

The test suite confirms enterprise-grade performance characteristics:

1. **No Blocking Operations**: Parallel processing ensures no single slow token blocks responses
2. **Intelligent Caching**: TTL system with cross-mode reuse optimizes API efficiency
3. **Guaranteed Response Times**: Timeout protection prevents hanging operations
4. **Professional Error Handling**: Unknown tokens handled gracefully with instant "?" responses
5. **Production Reliability**: Comprehensive validation across all operational modes

### Performance Metrics

- **Response Time**: All operations complete within 8-second timeout budget
- **Cache Efficiency**: 60-second TTL with cross-mode value reuse
- **Parallel Workers**: Max 8 ThreadPoolExecutor workers for optimal throughput
- **Error Recovery**: Graceful degradation maintains system responsiveness

This test suite ensures the Mork F.E.T.C.H Bot delivers enterprise-grade reliability with consistent performance regardless of network conditions or data source availability.
