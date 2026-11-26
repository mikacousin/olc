//! End-to-end test: a mock OLC (PUB for levels, REP for patch) publishes
//! in the real `engine.py` format, and the visualizer receiver must reconstruct
//! levels and patch in shared state.

use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

use bytes::Bytes;
use serde_json::json;
use viz_core::FixtureType;
use viz_source::{zmq, DmxSource, SharedState, VizCommand};
use zeromq::{PubSocket, RepSocket, Socket, SocketRecv, SocketSend, ZmqMessage};

const PUB_ENDPOINT: &str = "tcp://127.0.0.1:55571";
const REP_ENDPOINT: &str = "tcp://127.0.0.1:55572";

fn patch_json(version: u64) -> String {
    json!({
        "version": version,
        "stage": {
            "width": 16.0,
            "depth": 12.0,
            "color": "#111215",
            "grid_spacing": 0.5,
            "fog_density": 0.55
        },
        "devices": [
            {"id": 101, "label": "Face jardin", "manufacturer": "Robe",
             "model": "Robin 600", "mode": "Mode 1", "gdtf": "Robe@Robin600",
             "fixture_type": "moving_head",
             "universe": 2, "address": 17, "footprint": 24,
             "position": [-2.0, -3.0, 5.0],
             "focus_point": [1.0, 0.0, 0.0],
             "orientation": [0.0, 0.0, 0.0],
             "beam_angle": 20.0,
             "channels": [
                 {"type": "intensity", "universe": 2, "address": 17},
                 {"type": "pan", "universe": 2, "address": 18, "physical_min": -270.0, "physical_max": 270.0}
             ]},
            {"id": 5, "label": "Dim 5", "manufacturer": "Generic", "model": "Dimmer",
             "fixture_type": "dimmer",
             "universe": 1, "address": 5, "footprint": 1}
        ]
    })
    .to_string()
}

fn universe_message(universe: u16, frames: u64, level0: u8, patch_version: u64) -> ZmqMessage {
    let meta = json!({
        "hz": 44.0,
        "frames": frames,
        "protocols": ["Art-Net"],
        "active_universes": [universe],
        "patch_version": patch_version,
    });
    let mut frame = vec![0u8; 512];
    frame[0] = level0;
    frame[511] = 200;

    let mut msg = ZmqMessage::from(format!("universe:{universe}"));
    msg.push_back(Bytes::from(meta.to_string()));
    msg.push_back(Bytes::from(frame));
    msg
}

#[test]
fn receives_levels_and_patch_from_olc_format() {
    let state = SharedState::new();
    zmq::spawn(
        state.clone(),
        zmq::ZmqConfig {
            endpoint: PUB_ENDPOINT.to_string(),
            patch_endpoint: Some(REP_ENDPOINT.to_string()),
        },
    );

    let rt = tokio::runtime::Builder::new_current_thread()
        .enable_all()
        .build()
        .unwrap();

    let received_cmds: Arc<Mutex<Vec<String>>> = Arc::new(Mutex::new(Vec::new()));
    let cmds_clone = received_cmds.clone();

    rt.block_on(async {
        let mut publisher = PubSocket::new();
        publisher.bind(PUB_ENDPOINT).await.expect("bind pub");

        // Mock snapshot server: replies with current patch (version 3) and records commands.
        let mut rep = RepSocket::new();
        rep.bind(REP_ENDPOINT).await.expect("bind rep");
        tokio::spawn(async move {
            loop {
                let Ok(request) = rep.recv().await else { break };
                let bytes = request.get(0).map(|b| b.as_ref()).unwrap_or_default();
                let reply = if bytes == b"patch" {
                    ZmqMessage::from(patch_json(3))
                } else {
                    let txt = String::from_utf8_lossy(bytes).to_string();
                    cmds_clone.lock().unwrap().push(txt);
                    ZmqMessage::from(r#"{"ok":true}"#)
                };
                if rep.send(reply).await.is_err() {
                    break;
                }
            }
        });

        // A late-joining subscriber misses initial messages:
        // keep republishing until fully received or deadline expires.
        let deadline = Instant::now() + Duration::from_secs(10);
        let mut frames: u64 = 0;
        while (state.universe(5).is_none() || state.patch_version() != 3)
            && Instant::now() < deadline
        {
            publisher
                .send(universe_message(5, frames, 9, 3))
                .await
                .expect("send");
            frames += 1;
            tokio::time::sleep(Duration::from_millis(50)).await;
        }

        // Universe removed on OLC side: empty payload, deleted = true.
        let meta = json!({"hz": 44.0, "frames": frames, "protocols": [],
                          "deleted": true, "active_universes": []});
        let mut gone = ZmqMessage::from("universe:5");
        gone.push_back(Bytes::from(meta.to_string()));
        gone.push_back(Bytes::new());
        for _ in 0..20 {
            if state.universe(5).is_none() {
                break;
            }
            publisher.send(gone.clone()).await.expect("send deleted");
            tokio::time::sleep(Duration::from_millis(50)).await;
        }

        assert!(state.send_command(VizCommand::SetFocus {
            device_id: 101,
            target: [2.5, -1.0, 0.0],
            commit: true,
        }));
        let deadline = Instant::now() + Duration::from_secs(3);
        while received_cmds.lock().unwrap().is_empty() && Instant::now() < deadline {
            tokio::time::sleep(Duration::from_millis(20)).await;
        }
    });

    assert!(state.status().frames >= 1);
    assert_eq!(state.status().hz, 44.0);

    let patch = state.patch();
    assert_eq!(patch.version, 3);
    assert_eq!(patch.stage.width, 16.0);
    assert_eq!(patch.stage.fog_density, 0.55);
    assert_eq!(patch.fixtures.len(), 2);
    assert_eq!(patch.fixtures[0].channel, Some(101));
    assert_eq!(patch.fixtures[0].fixture_type, FixtureType::MovingHead);
    assert_eq!(patch.fixtures[0].position.z, 5.0);
    assert_eq!(patch.fixtures[0].focus_point.x, 1.0);
    assert_eq!(patch.fixtures[0].beam_angle, 20.0);
    assert_eq!(patch.fixtures[0].channels.len(), 2);
    assert_eq!(patch.fixtures[0].gdtf.as_deref(), Some("Robe@Robin600"));

    assert!(
        state.universe(5).is_none(),
        "deleted universe must disappear from state"
    );

    let cmds = received_cmds.lock().unwrap();
    assert_eq!(cmds.len(), 1);
    assert!(cmds[0].contains(r#""cmd":"set_focus""#));
    assert!(cmds[0].contains(r#""device_id":101"#));
}
