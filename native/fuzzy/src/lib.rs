mod normalization;

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::panic::{catch_unwind, AssertUnwindSafe};

fn guarded<T>(operation: impl FnOnce() -> T) -> PyResult<T> {
    catch_unwind(AssertUnwindSafe(operation))
        .map_err(|_| PyRuntimeError::new_err("Rust fuzzy matching failed; no result was produced"))
}

fn normalize_text(text: &str) -> String {
    let mapped: String = text
        .chars()
        .map(|ch| {
            let code = ch as u32;
            let ranges = normalization::RANGES;
            let index = ranges.partition_point(|&(start, _, _)| start <= code);
            if index > 0 {
                let (_, end, delta) = ranges[index - 1];
                if code <= end {
                    return char::from_u32((i64::from(code) + i64::from(delta)) as u32)
                        .expect("validated normalization table");
                }
            }
            ' '
        })
        .collect();
    mapped.trim_matches(' ').to_owned()
}

#[pyfunction]
fn normalize(py: Python<'_>, text: String) -> PyResult<String> {
    py.detach(|| guarded(|| normalize_text(&text)))
}

#[pyfunction]
fn process_and_ratio(
    py: Python<'_>,
    first: String,
    second: String,
    score_cutoff: f64,
) -> PyResult<f64> {
    py.detach(|| {
        guarded(|| {
            let first = normalize_text(&first);
            let second = normalize_text(&second);
            rapidfuzz::fuzz::ratio_with_args(
                first.chars(),
                second.chars(),
                &rapidfuzz::fuzz::Args::default().score_cutoff(score_cutoff / 100.0),
            )
            .unwrap_or(0.0)
                * 100.0
        })
    })
}

#[pymodule]
fn _native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("API_VERSION", 1)?;
    module.add_function(wrap_pyfunction!(normalize, module)?)?;
    module.add_function(wrap_pyfunction!(process_and_ratio, module)?)?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn normalization_is_context_independent() {
        assert_eq!(normalize_text("  İΟΣ e\u{301} 😀  "), "iοσ e");
        assert_eq!(normalize_text("!!!"), "");
        assert_eq!(normalize_text("A--B"), "a  b");
    }

    #[test]
    fn panics_are_caught() {
        Python::initialize();
        Python::attach(|py| {
            let error = guarded(|| panic!("synthetic failure")).unwrap_err();
            assert!(error.is_instance_of::<PyRuntimeError>(py));
        });
    }
}
