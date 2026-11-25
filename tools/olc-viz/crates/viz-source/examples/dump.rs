//! Diagnostic sans interface : se connecte à OLC et affiche ce qui arrive.
//!
//! cargo run -p viz-source --example dump -- [tcp://127.0.0.1:5555] [secondes]

use std::time::{Duration, Instant};

use viz_source::{zmq, DmxSource, SharedState};

fn main() {
    let mut args = std::env::args().skip(1);
    let endpoint = args
        .next()
        .unwrap_or_else(|| zmq::DEFAULT_ENDPOINT.to_string());
    let seconds: u64 = args.next().and_then(|s| s.parse().ok()).unwrap_or(5);

    let state = SharedState::new();
    zmq::spawn(state.clone(), zmq::ZmqConfig::new(endpoint.clone()));
    println!("écoute sur {endpoint} pendant {seconds} s…");

    let end = Instant::now() + Duration::from_secs(seconds);
    while Instant::now() < end {
        std::thread::sleep(Duration::from_millis(500));
    }

    let status = state.status();
    println!(
        "connecté : {} · {} trames · {:.0} Hz",
        status.connected, status.frames, status.hz
    );
    for u in state.universes() {
        if let Some(frame) = state.universe(u) {
            let active = frame.iter().filter(|&&v| v > 0).count();
            println!("univers {u} : {active} canaux non nuls");
        }
    }
    let patch = state.patch();
    println!(
        "patch v{} : {} projecteurs",
        patch.version,
        patch.fixtures.len()
    );
    for f in patch.fixtures.iter().take(10) {
        let addr = f
            .address
            .map(|a| format!("{}.{}", a.universe, a.channel))
            .unwrap_or_default();
        println!(
            "  #{:<5} {:<24} {:<8} {}",
            f.channel.unwrap_or(0),
            f.name,
            addr,
            f.gdtf.as_deref().unwrap_or("-")
        );
    }
}
